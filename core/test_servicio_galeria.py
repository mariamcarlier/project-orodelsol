"""Pruebas de `core.servicio_galeria` (Paso 03b).

Cada prueba escribe en una carpeta temporal (`MEDIA_ROOT` aislado), nunca en
`media/` del proyecto, y la borra al terminar. Las fotografías se fabrican en
memoria con Pillow.
"""

import shutil
import tempfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest import mock

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from . import servicio_galeria as galeria
from .models import Coleccion, Producto, ProductoImagen
from .servicio_galeria import MAX_IMAGENES_POR_PRODUCTO


def crear_producto(nombre="Anillo Aurora"):
    coleccion, _ = Coleccion.objects.get_or_create(nombre="Alma Dorada")
    return Producto.objects.create(
        coleccion=coleccion, nombre=nombre, precio=Decimal("1000000.00")
    )


def foto(nombre="foto.png", color=(200, 150, 50), tamano=(120, 80)):
    salida = BytesIO()
    Image.new("RGB", tamano, color).save(salida, format="PNG")
    return SimpleUploadedFile(nombre, salida.getvalue(), content_type="image/png")


def fotos(cantidad):
    return [foto(f"f{i}.png", color=(i * 30 % 255, 100, 50)) for i in range(cantidad)]


def url(n):
    return f"https://example.com/{n}.jpg"



class _Base(TestCase):
    def setUp(self):
        carpeta = tempfile.mkdtemp(prefix="galeria-test-")
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        sobreescritura = override_settings(MEDIA_ROOT=carpeta)
        sobreescritura.enable()
        self.addCleanup(sobreescritura.disable)
        self.media = Path(carpeta)
        self.producto = crear_producto()

    # ---- ayudas de comprobación -------------------------------------------------
    def filas(self, producto=None):
        return list(ProductoImagen.objects.filter(producto=producto or self.producto))

    def archivos_en_disco(self):
        return sorted(p for p in self.media.rglob("*") if p.is_file())

    def assertGaleriaConsistente(self, producto=None):
        filas = self.filas(producto)
        self.assertEqual([f.orden for f in filas], list(range(len(filas))))
        self.assertEqual(sum(f.es_principal for f in filas), 1 if filas else 0)
        self.assertLessEqual(len(filas), MAX_IMAGENES_POR_PRODUCTO)

    def assertNoPertenece(self, funcion, *args):
        with self.assertRaises(ValidationError) as ctx:
            funcion(*args)
        self.assertEqual(ctx.exception.code, "no_pertenece")

    def estado(self):
        return [(f.pk, f.orden, f.es_principal) for f in self.filas()]


class AgregarArchivosTests(_Base):
    def test_la_primera_fotografia_queda_como_principal_y_se_guardan_tres_archivos(self):
        creadas = galeria.agregar_archivos(self.producto, [foto()])

        self.assertEqual(len(creadas), 1)
        imagen = self.filas()[0]
        self.assertTrue(imagen.es_principal)
        self.assertEqual(imagen.orden, 0)
        for campo in (imagen.archivo, imagen.archivo_detalle, imagen.archivo_miniatura):
            self.assertTrue(default_storage.exists(campo.name))
            self.assertTrue(campo.name.startswith(f"productos/{self.producto.pk}/"))
        self.assertEqual(len(self.archivos_en_disco()), 3)
        self.assertGaleriaConsistente()

    def test_el_nombre_del_usuario_nunca_llega_al_disco(self):
        galeria.agregar_archivos(self.producto, [foto("../../etc/passwd mía.png")])

        for ruta in self.archivos_en_disco():
            self.assertNotIn("passwd", ruta.name)
            self.assertNotIn("mía", ruta.name)

    def test_marca_el_producto_como_galeria_gestionada(self):
        self.assertFalse(self.producto.galeria_gestionada)

        galeria.agregar_archivos(self.producto, [foto()])

        self.assertTrue(self.producto.galeria_gestionada)
        self.producto.refresh_from_db()
        self.assertTrue(self.producto.galeria_gestionada)

    def test_varias_a_la_vez_solo_la_primera_es_principal_y_conservan_el_orden(self):
        galeria.agregar_archivos(self.producto, fotos(3))

        filas = self.filas()
        self.assertEqual([f.es_principal for f in filas], [True, False, False])
        self.assertEqual([f.orden for f in filas], [0, 1, 2])

    def test_un_segundo_envio_se_agrega_al_final_sin_cambiar_la_principal(self):
        galeria.agregar_archivos(self.producto, fotos(2))
        principal_antes = galeria.principal(self.producto).pk

        galeria.agregar_archivos(self.producto, fotos(2))

        self.assertEqual(len(self.filas()), 4)
        self.assertEqual(galeria.principal(self.producto).pk, principal_antes)
        self.assertGaleriaConsistente()

    def test_sin_archivos_no_cambia_nada(self):
        self.assertEqual(galeria.agregar_archivos(self.producto, []), [])

        self.assertEqual(self.filas(), [])
        self.producto.refresh_from_db()
        self.assertFalse(self.producto.galeria_gestionada)

    def test_admite_exactamente_el_maximo_y_rechaza_una_mas(self):
        galeria.agregar_archivos(self.producto, fotos(MAX_IMAGENES_POR_PRODUCTO))
        self.assertEqual(len(self.filas()), MAX_IMAGENES_POR_PRODUCTO)
        archivos_antes = self.archivos_en_disco()

        with self.assertRaises(ValidationError) as ctx:
            galeria.agregar_archivos(self.producto, fotos(1))

        self.assertEqual(ctx.exception.code, "limite")
        self.assertEqual(len(self.filas()), MAX_IMAGENES_POR_PRODUCTO)
        self.assertEqual(self.archivos_en_disco(), archivos_antes)

    def test_un_envio_que_se_pasa_del_maximo_no_guarda_ninguna(self):
        galeria.agregar_archivos(self.producto, fotos(3))
        archivos_antes = self.archivos_en_disco()

        with self.assertRaises(ValidationError) as ctx:
            galeria.agregar_archivos(self.producto, fotos(MAX_IMAGENES_POR_PRODUCTO - 2))

        self.assertEqual(ctx.exception.code, "limite")
        self.assertEqual(len(self.filas()), 3)
        self.assertEqual(self.archivos_en_disco(), archivos_antes)

    def test_las_url_cuentan_para_el_maximo(self):
        for n in range(MAX_IMAGENES_POR_PRODUCTO - 1):
            galeria.agregar_url(self.producto, url(n))

        with self.assertRaises(ValidationError) as ctx:
            galeria.agregar_archivos(self.producto, fotos(2))

        self.assertEqual(ctx.exception.code, "limite")
        galeria.agregar_archivos(self.producto, fotos(1))  # una sí cabe
        self.assertGaleriaConsistente()

    def test_si_una_fotografia_no_es_valida_no_entra_ninguna(self):
        invalida = SimpleUploadedFile("rota.png", b"no soy una imagen", content_type="image/png")

        with self.assertRaises(ValidationError) as ctx:
            galeria.agregar_archivos(self.producto, [foto("buena.png"), invalida])

        self.assertIn("rota.png", ctx.exception.messages[0])
        self.assertEqual(self.filas(), [])
        self.assertEqual(self.archivos_en_disco(), [])
        self.producto.refresh_from_db()
        self.assertFalse(self.producto.galeria_gestionada)

    def test_un_envio_demasiado_pesado_se_rechaza_completo(self):
        with mock.patch("core.imagenes.MAX_BYTES_POR_ENVIO", 100):
            with self.assertRaises(ValidationError) as ctx:
                galeria.agregar_archivos(self.producto, fotos(2))

        self.assertEqual(ctx.exception.code, "envio_pesado")
        self.assertEqual(self.filas(), [])

    def test_si_falla_a_mitad_se_revierte_la_base_y_se_borran_los_archivos(self):
        with mock.patch.object(galeria, "_marcar_gestionada", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                galeria.agregar_archivos(self.producto, fotos(2))

        self.assertEqual(self.filas(), [])
        self.assertEqual(self.archivos_en_disco(), [])

    def test_si_otro_administrador_llena_la_galeria_mientras_se_procesa_se_rechaza(self):
        # Simula la ventana entre la comprobación previa y el bloqueo: mientras
        # se procesan las imágenes, «otra persona» añade fotografías.
        original = galeria._procesar_todas

        def procesar_y_colarse(archivos):
            resultado = original(archivos)
            for n in range(MAX_IMAGENES_POR_PRODUCTO):
                ProductoImagen.objects.create(
                    producto=self.producto, url=url(n), orden=n, es_principal=n == 0
                )
            return resultado

        with mock.patch.object(galeria, "_procesar_todas", procesar_y_colarse):
            with self.assertRaises(ValidationError) as ctx:
                galeria.agregar_archivos(self.producto, fotos(1))

        self.assertEqual(ctx.exception.code, "limite")
        self.assertEqual(len(self.filas()), MAX_IMAGENES_POR_PRODUCTO)
        self.assertEqual(self.archivos_en_disco(), [])

    def test_no_toca_la_galeria_de_otros_productos(self):
        otro = crear_producto("Otro anillo")
        galeria.agregar_archivos(otro, fotos(2))
        estado_otro = [(f.pk, f.orden, f.es_principal) for f in self.filas(otro)]

        galeria.agregar_archivos(self.producto, fotos(2))

        self.assertEqual(
            [(f.pk, f.orden, f.es_principal) for f in self.filas(otro)], estado_otro
        )
        self.assertGaleriaConsistente(otro)
        self.assertGaleriaConsistente(self.producto)


class AgregarUrlTests(_Base):
    def test_agrega_una_url_como_principal_y_sin_archivos(self):
        imagen = galeria.agregar_url(self.producto, "  https://example.com/a.jpg  ")

        self.assertEqual(imagen.url, "https://example.com/a.jpg")
        self.assertTrue(imagen.es_principal)
        self.assertFalse(imagen.archivo)
        self.assertTrue(self.producto.galeria_gestionada)
        self.assertEqual(self.archivos_en_disco(), [])

    def test_la_galeria_puede_mezclar_archivos_y_url(self):
        galeria.agregar_url(self.producto, url(1))
        galeria.agregar_archivos(self.producto, fotos(1))
        galeria.agregar_url(self.producto, url(2))

        self.assertEqual([bool(f.archivo) for f in self.filas()], [False, True, False])
        self.assertGaleriaConsistente()

    def test_rechaza_direcciones_que_no_son_http_o_https(self):
        malas = [
            "",
            "   ",
            None,
            "ftp://example.com/a.jpg",
            "javascript:alert(1)",
            "data:image/png;base64,AAAA",
            "file:///etc/passwd",
            "//example.com/a.jpg",
            "example.com/a.jpg",
            "https://",
        ]
        for mala in malas:
            with self.subTest(url=mala):
                with self.assertRaises(ValidationError) as ctx:
                    galeria.agregar_url(self.producto, mala)
                self.assertEqual(ctx.exception.code, "url_invalida")
        self.assertEqual(self.filas(), [])

    def test_rechaza_una_url_mas_larga_que_el_campo(self):
        larga = "https://example.com/" + "a" * galeria.LARGO_MAXIMO_URL

        with self.assertRaises(ValidationError) as ctx:
            galeria.agregar_url(self.producto, larga)

        self.assertEqual(ctx.exception.code, "url_invalida")

    def test_rechaza_una_mas_que_el_maximo(self):
        for n in range(MAX_IMAGENES_POR_PRODUCTO):
            galeria.agregar_url(self.producto, url(n))

        with self.assertRaises(ValidationError) as ctx:
            galeria.agregar_url(self.producto, url(99))

        self.assertEqual(ctx.exception.code, "limite")
        self.assertEqual(len(self.filas()), MAX_IMAGENES_POR_PRODUCTO)


class EstablecerPrincipalTests(_Base):
    def setUp(self):
        super().setUp()
        galeria.agregar_archivos(self.producto, fotos(3))
        self.a, self.b, self.c = self.filas()

    def test_cambia_la_principal_y_la_anterior_deja_de_serlo(self):
        galeria.establecer_principal(self.producto, self.c.pk)

        self.assertEqual(galeria.principal(self.producto).pk, self.c.pk)
        self.assertGaleriaConsistente()

    def test_no_mueve_las_fotografias_de_lugar(self):
        galeria.establecer_principal(self.producto, self.c.pk)

        self.assertEqual([f.pk for f in self.filas()], [self.a.pk, self.b.pk, self.c.pk])

    def test_repetir_con_la_misma_principal_no_cambia_nada(self):
        antes = self.estado()

        galeria.establecer_principal(self.producto, self.a.pk)

        self.assertEqual(self.estado(), antes)

    def test_rechaza_la_fotografia_de_otro_producto_sin_cambiar_nada(self):
        otro = crear_producto("Otro")
        ajena = galeria.agregar_url(otro, url(1))
        antes = self.estado()

        self.assertNoPertenece(galeria.establecer_principal, self.producto, ajena.pk)

        self.assertEqual(self.estado(), antes)
        self.assertTrue(self.filas(otro)[0].es_principal)

    def test_rechaza_identificadores_inexistentes_o_mal_formados(self):
        for malo in (999999, 0, -1, "abc", None, "1; DROP TABLE"):
            with self.subTest(id=malo):
                self.assertNoPertenece(galeria.establecer_principal, self.producto, malo)


class ReordenarTests(_Base):
    def setUp(self):
        super().setUp()
        galeria.agregar_archivos(self.producto, fotos(3))
        self.a, self.b, self.c = self.filas()

    def ids(self):
        return [f.pk for f in self.filas()]

    def test_intercambia_dos_posiciones(self):
        galeria.reordenar(self.producto, {self.a.pk: 1, self.b.pk: 0})

        self.assertEqual(self.ids(), [self.b.pk, self.a.pk, self.c.pk])
        self.assertGaleriaConsistente()

    def test_poner_una_fotografia_en_la_posicion_cero_la_deja_primera(self):
        galeria.reordenar(self.producto, {self.c.pk: 0})

        self.assertEqual(self.ids(), [self.c.pk, self.a.pk, self.b.pk])
        self.assertGaleriaConsistente()

    def test_acepta_numeros_enviados_como_texto_y_normaliza_valores_grandes(self):
        galeria.reordenar(
            self.producto, {str(self.a.pk): "30", str(self.b.pk): "10", str(self.c.pk): "20"}
        )

        self.assertEqual(self.ids(), [self.b.pk, self.c.pk, self.a.pk])
        self.assertGaleriaConsistente()

    def test_bajar_una_fotografia_la_deja_en_la_posicion_pedida(self):
        # Antes, «mover la primera a la posición 1» no cambiaba nada y «a la 2»
        # la dejaba en la 1: al bajar, la fotografía quedaba un lugar antes.
        galeria.reordenar(self.producto, {self.a.pk: 1})
        self.assertEqual(self.ids(), [self.b.pk, self.a.pk, self.c.pk])

        galeria.reordenar(self.producto, {self.b.pk: 2})
        self.assertEqual(self.ids(), [self.a.pk, self.c.pk, self.b.pk])
        self.assertGaleriaConsistente()

    def test_una_posicion_mayor_que_la_galeria_la_manda_al_final(self):
        galeria.reordenar(self.producto, {self.a.pk: 99})

        self.assertEqual(self.ids(), [self.b.pk, self.c.pk, self.a.pk])
        self.assertGaleriaConsistente()

    def test_dos_movidas_a_la_misma_posicion_quedan_seguidas_en_su_orden_previo(self):
        galeria.reordenar(self.producto, {self.a.pk: 2, self.b.pk: 2})

        self.assertEqual(self.ids(), [self.c.pk, self.a.pk, self.b.pk])
        self.assertGaleriaConsistente()

    def test_dos_movidas_al_mismo_lugar_intermedio_no_se_invierten(self):
        d, e = galeria.agregar_archivos(self.producto, fotos(2))

        galeria.reordenar(self.producto, {d.pk: 1, e.pk: 1})

        self.assertEqual(self.ids(), [self.a.pk, d.pk, e.pk, self.b.pk, self.c.pk])
        self.assertGaleriaConsistente()

    def test_varias_movidas_terminan_cada_una_en_su_lugar(self):
        d, e = galeria.agregar_archivos(self.producto, fotos(2))

        galeria.reordenar(self.producto, {self.a.pk: 3, e.pk: 0})

        self.assertEqual(self.ids(), [e.pk, self.b.pk, self.c.pk, self.a.pk, d.pk])
        self.assertGaleriaConsistente()

    def test_sin_posiciones_solo_normaliza(self):
        ProductoImagen.objects.filter(pk=self.c.pk).update(orden=40)

        galeria.reordenar(self.producto, {})

        self.assertEqual(self.ids(), [self.a.pk, self.b.pk, self.c.pk])
        self.assertGaleriaConsistente()

    def test_no_cambia_cual_es_la_principal(self):
        principal = galeria.principal(self.producto).pk

        galeria.reordenar(self.producto, {self.c.pk: 0})

        self.assertEqual(galeria.principal(self.producto).pk, principal)

    def test_los_empates_se_resuelven_por_el_orden_previo(self):
        galeria.reordenar(self.producto, {self.a.pk: 5, self.b.pk: 5, self.c.pk: 5})

        self.assertEqual(self.ids(), [self.a.pk, self.b.pk, self.c.pk])

    def test_un_valor_invalido_no_cambia_nada(self):
        antes = self.estado()
        invalidos = ["abc", -1, 32768, None, True, "1.5", [1]]
        for invalido in invalidos:
            with self.subTest(valor=invalido):
                with self.assertRaises(ValidationError) as ctx:
                    galeria.reordenar(self.producto, {self.a.pk: 0, self.b.pk: invalido})
                self.assertEqual(ctx.exception.code, "orden")
                self.assertEqual(self.estado(), antes)

    def test_un_id_ajeno_cancela_toda_la_operacion(self):
        otro = crear_producto("Otro")
        ajena = galeria.agregar_url(otro, url(1))
        antes = self.estado()
        antes_otro = [(f.pk, f.orden) for f in self.filas(otro)]

        self.assertNoPertenece(
            galeria.reordenar, self.producto, {self.a.pk: 2, ajena.pk: 0}
        )

        self.assertEqual(self.estado(), antes)
        self.assertEqual([(f.pk, f.orden) for f in self.filas(otro)], antes_otro)

    def test_rechaza_algo_que_no_es_un_diccionario(self):
        with self.assertRaises(ValidationError):
            galeria.reordenar(self.producto, [self.a.pk, self.b.pk])


class EliminarImagenTests(_Base):
    def setUp(self):
        super().setUp()
        galeria.agregar_archivos(self.producto, fotos(3))
        self.a, self.b, self.c = self.filas()

    def eliminar(self, imagen):
        with self.captureOnCommitCallbacks(execute=True):
            galeria.eliminar_imagen(self.producto, imagen.pk)

    def test_eliminar_una_no_principal_renumera_y_conserva_la_principal(self):
        self.eliminar(self.b)

        self.assertEqual([f.pk for f in self.filas()], [self.a.pk, self.c.pk])
        self.assertEqual(galeria.principal(self.producto).pk, self.a.pk)
        self.assertGaleriaConsistente()

    def test_eliminar_la_principal_promueve_a_la_siguiente_por_orden(self):
        self.eliminar(self.a)

        self.assertEqual(galeria.principal(self.producto).pk, self.b.pk)
        self.assertGaleriaConsistente()

    def test_eliminar_la_principal_que_esta_al_final_promueve_a_la_primera(self):
        galeria.establecer_principal(self.producto, self.c.pk)

        self.eliminar(self.c)

        self.assertEqual(galeria.principal(self.producto).pk, self.a.pk)
        self.assertGaleriaConsistente()

    def test_eliminar_la_ultima_deja_la_galeria_vacia_y_gestionada(self):
        for imagen in (self.a, self.b, self.c):
            self.eliminar(imagen)

        self.assertEqual(self.filas(), [])
        self.assertIsNone(galeria.principal(self.producto))
        self.producto.refresh_from_db()
        self.assertTrue(self.producto.galeria_gestionada)

    def test_se_borran_del_disco_los_tres_archivos_pero_solo_tras_confirmar(self):
        self.assertEqual(len(self.archivos_en_disco()), 9)

        with self.captureOnCommitCallbacks(execute=False) as pendientes:
            galeria.eliminar_imagen(self.producto, self.b.pk)
        self.assertEqual(len(self.archivos_en_disco()), 9)  # aún no se confirmó

        for callback in pendientes:
            callback()
        self.assertEqual(len(self.archivos_en_disco()), 6)
        self.assertFalse(default_storage.exists(self.b.archivo.name))
        self.assertTrue(default_storage.exists(self.a.archivo.name))

    def test_eliminar_una_url_no_toca_el_disco(self):
        imagen = galeria.agregar_url(self.producto, url(1))
        archivos_antes = self.archivos_en_disco()

        self.eliminar(imagen)

        self.assertEqual(self.archivos_en_disco(), archivos_antes)
        self.assertGaleriaConsistente()

    def test_no_borra_archivos_fuera_de_la_carpeta_del_producto(self):
        ajeno = self.media / "otra-carpeta" / "ajeno.png"
        ajeno.parent.mkdir()
        ajeno.write_bytes(b"importante")
        ProductoImagen.objects.filter(pk=self.b.pk).update(archivo="otra-carpeta/ajeno.png")

        with self.assertLogs("core.servicio_galeria", level="WARNING"):
            self.eliminar(self.b)

        self.assertTrue(ajeno.exists())

    def test_no_borra_archivos_de_la_carpeta_de_otro_producto(self):
        otro = crear_producto("Otro")
        galeria.agregar_archivos(otro, fotos(1))
        de_otro = self.filas(otro)[0].archivo.name
        ProductoImagen.objects.filter(pk=self.b.pk).update(archivo=de_otro)

        with self.assertLogs("core.servicio_galeria", level="WARNING"):
            self.eliminar(self.b)

        self.assertTrue(default_storage.exists(de_otro))

    def test_rechaza_la_fotografia_de_otro_producto(self):
        otro = crear_producto("Otro")
        ajena = galeria.agregar_url(otro, url(1))
        antes = self.estado()

        self.assertNoPertenece(galeria.eliminar_imagen, self.producto, ajena.pk)

        self.assertEqual(self.estado(), antes)
        self.assertEqual(len(self.filas(otro)), 1)

    def test_tras_eliminar_se_puede_volver_a_llenar_hasta_el_maximo(self):
        self.eliminar(self.a)
        galeria.agregar_archivos(self.producto, fotos(MAX_IMAGENES_POR_PRODUCTO - 2))

        self.assertEqual(len(self.filas()), MAX_IMAGENES_POR_PRODUCTO)
        self.assertGaleriaConsistente()


class NormalizarYConsultaTests(_Base):
    def test_repara_huecos_de_orden_y_falta_de_principal(self):
        for n, orden in enumerate((7, 3, 9)):
            ProductoImagen.objects.create(
                producto=self.producto, url=url(n), orden=orden, es_principal=False
            )

        galeria.normalizar(self.producto)

        self.assertEqual([f.url for f in self.filas()], [url(1), url(0), url(2)])
        self.assertGaleriaConsistente()
        self.assertEqual(galeria.principal(self.producto).url, url(1))

    def test_es_idempotente_y_no_hace_nada_en_una_galeria_vacia(self):
        galeria.normalizar(self.producto)
        self.assertEqual(self.filas(), [])

        galeria.agregar_url(self.producto, url(1))
        antes = self.estado()
        galeria.normalizar(self.producto)
        galeria.normalizar(self.producto)

        self.assertEqual(self.estado(), antes)

    def test_listar_devuelve_el_orden_de_visualizacion(self):
        galeria.agregar_archivos(self.producto, fotos(3))
        a, b, c = self.filas()
        galeria.reordenar(self.producto, {c.pk: 0})

        self.assertEqual([i.pk for i in galeria.listar(self.producto)], [c.pk, a.pk, b.pk])

    def test_listar_por_producto_agrupa_varias_galerias_con_una_consulta(self):
        otro = crear_producto("Anillo Brisa")
        sin_galeria = crear_producto("Anillo Cielo")
        galeria.agregar_archivos(self.producto, fotos(3))
        a, b, c = self.filas()
        galeria.reordenar(self.producto, {c.pk: 0})
        de_otro = galeria.agregar_url(otro, url(1))

        with self.assertNumQueries(1):
            galerias = galeria.listar_por_producto([self.producto, otro, sin_galeria])

        self.assertEqual(
            {pk: [imagen.pk for imagen in imagenes] for pk, imagenes in galerias.items()},
            {self.producto.pk: [c.pk, a.pk, b.pk], otro.pk: [de_otro.pk], sin_galeria.pk: []},
        )

    def test_listar_por_producto_sin_productos_no_falla(self):
        self.assertEqual(galeria.listar_por_producto([]), {})

    def test_principal_de_un_producto_sin_galeria_es_none(self):
        self.assertIsNone(galeria.principal(self.producto))

    def test_el_maximo_aprobado_no_cambia_por_accidente(self):
        # Aprobado para Joyas Oro del Sol: 10 fotografías por producto.
        self.assertEqual(MAX_IMAGENES_POR_PRODUCTO, 10)
