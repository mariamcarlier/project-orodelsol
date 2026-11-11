"""Pruebas de `core.imagenes` (Paso 03a). No usan base de datos ni disco.

Las imágenes se fabrican en memoria con Pillow. Los límites se leen de las
constantes del módulo, de modo que cambiar un límite no obliga a reescribir las
pruebas; lo que cada prueba fija es el COMPORTAMIENTO frente a ese límite.
"""

import warnings
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image, ImageCms, PngImagePlugin

from . import imagenes
from .imagenes import (
    LADO_DETALLE_PX,
    LADO_MINIATURA_PX,
    MAX_BYTES_POR_ENVIO,
    MAX_BYTES_POR_IMAGEN,
    MAX_LADO_PX,
    procesar_imagen,
    validar_envio,
    validar_imagen,
)


def _bytes(imagen, formato, **opciones):
    salida = BytesIO()
    imagen.save(salida, format=formato, **opciones)
    return salida.getvalue()


def _subido(datos, nombre="foto.jpg", tipo="image/jpeg"):
    return SimpleUploadedFile(nombre, datos, content_type=tipo)


def _foto(ancho=300, alto=200, modo="RGB", color=(200, 150, 50)):
    return Image.new(modo, (ancho, alto), color)


def _abrir(datos):
    imagen = Image.open(BytesIO(datos))
    imagen.load()
    return imagen


class _Base(SimpleTestCase):
    def assertRechaza(self, archivo, codigo):
        with self.assertRaises(ValidationError) as ctx:
            procesar_imagen(archivo)
        self.assertEqual(ctx.exception.code, codigo)
        # La validación sola debe llegar a la misma conclusión.
        archivo.seek(0)
        with self.assertRaises(ValidationError) as ctx2:
            validar_imagen(archivo)
        self.assertEqual(ctx2.exception.code, codigo)
        return ctx.exception.messages[0]


class FormatosAceptadosTests(_Base):
    def test_acepta_jpeg_png_y_webp(self):
        casos = [
            ("JPEG", ".jpg", "foto.jpg"),
            ("PNG", ".png", "foto.png"),
            ("WEBP", ".webp", "foto.webp"),
        ]
        for formato, extension, nombre in casos:
            with self.subTest(formato=formato):
                resultado = procesar_imagen(_subido(_bytes(_foto(), formato), nombre))
                self.assertEqual(resultado.formato, formato)
                self.assertEqual(resultado.extension_original, extension)
                self.assertEqual(_abrir(resultado.original).format, formato)

    def test_el_formato_se_decide_por_el_contenido_no_por_el_nombre(self):
        # Un PNG con nombre .jpg y tipo declarado jpeg sigue siendo un PNG.
        resultado = procesar_imagen(_subido(_bytes(_foto(), "PNG"), "engano.jpg", "image/jpeg"))
        self.assertEqual(resultado.formato, "PNG")
        self.assertEqual(resultado.extension_original, ".png")

    def test_rechaza_mpo_aunque_sea_un_jpeg_con_varias_fotos(self):
        # MPO (JPEG con varias fotos) queda fuera de la lista aprobada.
        datos = _bytes(_foto(), "MPO", save_all=True, append_images=[_foto(color=(1, 2, 3))])
        self.assertEqual(Image.open(BytesIO(datos)).format, "MPO")
        mensaje = self.assertRechaza(_subido(datos), "formato")
        self.assertIn("MPO", mensaje)

    def test_devuelve_las_dimensiones_de_la_imagen(self):
        resultado = procesar_imagen(_subido(_bytes(_foto(300, 200), "PNG"), "a.png"))
        self.assertEqual((resultado.ancho, resultado.alto), (300, 200))


class FormatosRechazadosTests(_Base):
    def test_rechaza_gif_bmp_y_tiff_aunque_se_llamen_jpg(self):
        for formato in ("GIF", "BMP", "TIFF"):
            with self.subTest(formato=formato):
                datos = _bytes(_foto(modo="RGB" if formato != "GIF" else "P"), formato)
                self.assertRechaza(_subido(datos, "foto.jpg"), "formato")

    def test_rechaza_gif_animado(self):
        cuadros = [_foto(color=(i * 40, 0, 0)).convert("P") for i in range(3)]
        datos = _bytes(cuadros[0], "GIF", save_all=True, append_images=cuadros[1:])
        self.assertRechaza(_subido(datos, "a.gif", "image/gif"), "formato")

    def test_rechaza_webp_animado(self):
        cuadros = [_foto(color=(i * 40, 0, 0)) for i in range(3)]
        datos = _bytes(cuadros[0], "WEBP", save_all=True, append_images=cuadros[1:], duration=50)
        mensaje = self.assertRechaza(_subido(datos, "a.webp", "image/webp"), "animada")
        self.assertIn("animadas", mensaje)

    def test_rechaza_png_animado(self):
        cuadros = [_foto(color=(i * 40, 0, 0)) for i in range(3)]
        datos = _bytes(cuadros[0], "PNG", save_all=True, append_images=cuadros[1:])
        self.assertRechaza(_subido(datos, "a.png", "image/png"), "animada")

    def test_rechaza_texto_html_y_svg_disfrazados_de_imagen(self):
        casos = {
            "html": b"<html><script>alert(1)</script></html>",
            "svg": b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        }
        for nombre, contenido in casos.items():
            with self.subTest(nombre):
                self.assertRechaza(_subido(contenido, "foto.png", "image/png"), "no_imagen")

    def test_rechaza_archivo_vacio(self):
        self.assertRechaza(_subido(b"", "vacia.jpg"), "vacio")

    def test_rechaza_imagen_truncada(self):
        datos = _bytes(_foto(800, 600, color=(10, 200, 90)), "JPEG")
        self.assertRechaza(_subido(datos[: len(datos) // 2]), "danada")

    def test_rechaza_bytes_aleatorios_con_cabecera_de_jpeg(self):
        self.assertRechaza(_subido(b"\xff\xd8\xff\xe0" + b"\x00" * 50), "no_imagen")


class LimitesTests(_Base):
    def test_rechaza_archivo_que_supera_el_peso_maximo(self):
        # PNG válido al que se le añade basura al final hasta pasar el tope.
        datos = _bytes(_foto(), "PNG") + b"0" * (MAX_BYTES_POR_IMAGEN + 1)
        mensaje = self.assertRechaza(_subido(datos, "grande.png"), "pesada")
        self.assertIn(str(MAX_BYTES_POR_IMAGEN // (1024 * 1024)), mensaje)

    def test_el_peso_se_mide_sobre_los_bytes_reales_no_sobre_lo_declarado(self):
        archivo = _subido(_bytes(_foto(), "PNG") + b"0" * (MAX_BYTES_POR_IMAGEN + 1), "a.png")
        archivo.size = 10  # un cliente mentiroso
        self.assertRechaza(archivo, "pesada")

    def test_acepta_un_archivo_justo_en_el_limite_de_peso(self):
        base = _bytes(_foto(), "PNG")
        datos = base + b"0" * (MAX_BYTES_POR_IMAGEN - len(base))
        self.assertEqual(len(datos), MAX_BYTES_POR_IMAGEN)
        # Pesa exactamente el máximo: no se rechaza por peso.
        self.assertEqual(procesar_imagen(_subido(datos, "a.png")).formato, "PNG")

    def test_rechaza_lado_mayor_al_maximo(self):
        datos = _bytes(Image.new("1", (MAX_LADO_PX + 1, 10)), "PNG")
        mensaje = self.assertRechaza(_subido(datos, "ancha.png"), "dimensiones")
        self.assertIn(f"{MAX_LADO_PX + 1}×10", mensaje)

    def test_acepta_lado_justo_en_el_maximo(self):
        datos = _bytes(Image.new("1", (MAX_LADO_PX, 10)), "PNG")
        self.assertEqual(procesar_imagen(_subido(datos, "a.png")).ancho, MAX_LADO_PX)

    def test_rechaza_demasiados_megapixeles_aunque_ningun_lado_pase_el_maximo(self):
        # 6500 × 6500 = 42,25 MP > 40 MP, con lados menores que 8000.
        datos = _bytes(Image.new("1", (6500, 6500)), "PNG")
        self.assertLess(len(datos), MAX_BYTES_POR_IMAGEN)
        self.assertRechaza(_subido(datos, "mp.png"), "dimensiones")

    def test_rechaza_bomba_de_descompresion_con_mensaje_de_dimensiones(self):
        # ~400 MP en un PNG de 1 bit pesa unos KB: debe rechazarse sin decodificarlo.
        datos = _bytes(Image.new("1", (20000, 20000)), "PNG")
        self.assertLess(len(datos), MAX_BYTES_POR_IMAGEN)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mensaje = self.assertRechaza(_subido(datos, "bomba.png"), "dimensiones")
        self.assertIn("megapíxeles", mensaje)

    def test_validar_envio_acepta_hasta_el_maximo_y_rechaza_mas(self):
        mitad = SimpleUploadedFile("a.jpg", b"0" * (MAX_BYTES_POR_ENVIO // 2))
        validar_envio([mitad, mitad])  # exactamente el máximo: válido
        with self.assertRaises(ValidationError) as ctx:
            validar_envio([mitad, mitad, SimpleUploadedFile("b.jpg", b"0")])
        self.assertEqual(ctx.exception.code, "envio_pesado")

    def test_validar_envio_sin_archivos_no_falla(self):
        validar_envio([])


class LimpiezaTests(_Base):
    def test_elimina_el_exif_incluida_la_ubicacion_gps(self):
        exif = Image.Exif()
        exif[0x010F] = "MarcaDeCamara"  # Make
        exif[0x8825] = {1: "N", 2: (4.0, 36.0, 0.0), 3: "W", 4: (74.0, 4.0, 0.0)}  # GPS
        datos = _bytes(_foto(), "JPEG", exif=exif)
        self.assertIn(0x8825, Image.open(BytesIO(datos)).getexif())  # la entrada sí lo traía

        resultado = procesar_imagen(_subido(datos))

        for nombre in ("original", "detalle", "miniatura"):
            with self.subTest(nombre):
                contenido = getattr(resultado, nombre)
                self.assertEqual(len(_abrir(contenido).getexif()), 0)
                self.assertNotIn(b"Exif", contenido)
                self.assertNotIn(b"MarcaDeCamara", contenido)

    def test_elimina_exif_y_xmp_tambien_en_png_y_webp(self):
        exif = Image.Exif()
        exif[0x010F] = "MarcaDeCamara"
        casos = [
            ("PNG", {"exif": exif}, "a.png"),
            ("WEBP", {"exif": exif, "xmp": b"<x>XmpPrivado</x>"}, "a.webp"),
        ]
        for formato, opciones, nombre in casos:
            with self.subTest(formato=formato):
                datos = _bytes(_foto(), formato, **opciones)
                self.assertIn(b"MarcaDeCamara", datos)  # el archivo de entrada sí lo traía

                resultado = procesar_imagen(_subido(datos, nombre))

                for parte in ("original", "detalle", "miniatura"):
                    contenido = getattr(resultado, parte)
                    self.assertNotIn(b"MarcaDeCamara", contenido)
                    self.assertNotIn(b"XmpPrivado", contenido)

    def test_aplica_la_orientacion_exif_antes_de_borrarla(self):
        exif = Image.Exif()
        exif[0x0112] = 6  # girada: hay que rotarla 90° para verla derecha
        datos = _bytes(_foto(300, 200), "JPEG", exif=exif)

        resultado = procesar_imagen(_subido(datos))

        self.assertEqual((resultado.ancho, resultado.alto), (200, 300))
        self.assertEqual(_abrir(resultado.original).size, (200, 300))
        self.assertEqual(len(_abrir(resultado.original).getexif()), 0)

    def test_quita_los_comentarios_de_texto_de_un_png(self):
        info = PngImagePlugin.PngInfo()
        info.add_text("Comentario", "dato-privado-123")
        datos = _bytes(_foto(), "PNG", pnginfo=info)
        self.assertIn(b"dato-privado-123", datos)

        resultado = procesar_imagen(_subido(datos, "a.png"))

        self.assertNotIn(b"dato-privado-123", resultado.original)

    def test_descarta_contenido_pegado_al_final_de_un_png_valido(self):
        # «Políglota»: un PNG válido seguido de un script. Se vuelve a codificar.
        carga = b"<script>alert(1)</script>"
        datos = _bytes(_foto(), "PNG") + carga

        resultado = procesar_imagen(_subido(datos, "a.png"))

        for nombre in ("original", "detalle", "miniatura"):
            self.assertNotIn(carga, getattr(resultado, nombre))

    def test_conserva_el_perfil_de_color_icc(self):
        perfil = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        datos = _bytes(_foto(), "JPEG", icc_profile=perfil)

        resultado = procesar_imagen(_subido(datos))

        self.assertEqual(_abrir(resultado.original).info.get("icc_profile"), perfil)
        self.assertEqual(_abrir(resultado.detalle).info.get("icc_profile"), perfil)


class DerivadosTests(_Base):
    def test_los_derivados_son_webp_y_respetan_su_lado_maximo(self):
        resultado = procesar_imagen(_subido(_bytes(_foto(3000, 2000), "JPEG")))

        detalle, miniatura = _abrir(resultado.detalle), _abrir(resultado.miniatura)
        self.assertEqual((detalle.format, miniatura.format), ("WEBP", "WEBP"))
        self.assertEqual(max(detalle.size), LADO_DETALLE_PX)
        self.assertEqual(max(miniatura.size), LADO_MINIATURA_PX)

    def test_los_derivados_conservan_la_proporcion(self):
        resultado = procesar_imagen(_subido(_bytes(_foto(3000, 2000), "JPEG")))

        self.assertEqual(_abrir(resultado.detalle).size, (1200, 800))
        self.assertEqual(_abrir(resultado.miniatura).size, (400, 267))

    def test_no_amplia_las_imagenes_pequenas(self):
        resultado = procesar_imagen(_subido(_bytes(_foto(300, 200), "JPEG")))

        self.assertEqual(_abrir(resultado.detalle).size, (300, 200))
        self.assertEqual(_abrir(resultado.miniatura).size, (300, 200))

    def test_el_original_no_se_reduce(self):
        resultado = procesar_imagen(_subido(_bytes(_foto(3000, 2000), "JPEG")))

        self.assertEqual(_abrir(resultado.original).size, (3000, 2000))

    def test_conserva_la_transparencia_de_un_png_rgba(self):
        imagen = Image.new("RGBA", (200, 100), (255, 0, 0, 0))
        resultado = procesar_imagen(_subido(_bytes(imagen, "PNG"), "a.png"))

        for nombre in ("original", "detalle", "miniatura"):
            with self.subTest(nombre):
                pixel = _abrir(getattr(resultado, nombre)).convert("RGBA").getpixel((10, 10))
                self.assertEqual(pixel[3], 0)

    def test_conserva_la_transparencia_de_un_png_de_paleta(self):
        imagen = Image.new("P", (200, 100), 0)
        imagen.putpalette([255, 0, 0] * 256)
        datos = _bytes(imagen, "PNG", transparency=0)

        resultado = procesar_imagen(_subido(datos, "a.png"))

        for nombre in ("original", "detalle"):
            with self.subTest(nombre):
                pixel = _abrir(getattr(resultado, nombre)).convert("RGBA").getpixel((10, 10))
                self.assertEqual(pixel[3], 0)

    def test_procesa_modos_poco_comunes_sin_fallar(self):
        casos = [
            ("CMYK", "JPEG", (0, 0, 0, 0)),
            ("L", "JPEG", 128),
            ("L", "PNG", 128),
            ("LA", "PNG", (128, 255)),
            ("1", "PNG", 1),
            ("L", "WEBP", 128),
        ]
        for modo, formato, color in casos:
            with self.subTest(modo=modo, formato=formato):
                imagen = Image.new(modo, (120, 80), color)
                resultado = procesar_imagen(_subido(_bytes(imagen, formato)))
                self.assertEqual(_abrir(resultado.original).format, formato)
                self.assertEqual(_abrir(resultado.detalle).format, "WEBP")
                self.assertEqual((resultado.ancho, resultado.alto), (120, 80))


class ArchivoSubidoTests(_Base):
    def test_el_archivo_queda_leible_desde_el_principio_despues_de_validar(self):
        datos = _bytes(_foto(), "JPEG")
        archivo = _subido(datos)

        validar_imagen(archivo)

        self.assertEqual(archivo.read(), datos)

    def test_se_puede_validar_dos_veces_el_mismo_archivo(self):
        archivo = _subido(_bytes(_foto(), "PNG"), "a.png")
        validar_imagen(archivo)
        self.assertEqual(procesar_imagen(archivo).formato, "PNG")

    def test_funciona_con_un_archivo_en_memoria_sin_atributo_size(self):
        buffer = BytesIO(b"0" * 10)
        validar_envio([buffer])  # `_tamano` recurre a seek/tell

    def test_los_limites_aprobados_no_cambiaron_por_accidente(self):
        # Si un día se cambian a propósito, se actualiza este test junto con la decisión.
        self.assertEqual(imagenes.MAX_BYTES_POR_IMAGEN, 10 * 1024 * 1024)
        self.assertEqual(imagenes.MAX_BYTES_POR_ENVIO, 30 * 1024 * 1024)
        self.assertEqual(imagenes.MAX_LADO_PX, 8000)
        self.assertEqual(imagenes.MAX_PIXELES, 40_000_000)
        self.assertEqual((imagenes.LADO_DETALLE_PX, imagenes.LADO_MINIATURA_PX), (1200, 400))
        self.assertEqual(
            imagenes.FORMATOS_PERMITIDOS, frozenset({"JPEG", "PNG", "WEBP"})
        )
