"""Portada de una colección (Paso 04): `core/portadas.py`, `Coleccion` y `ColeccionForm`.

Qué se comprueba aquí:
- El archivo que se sube pasa por `core.imagenes` y se guarda UNA versión WebP.
- La regla «un archivo o una dirección (URL), nunca los dos».
- El disco no se separa de la base de datos: al sustituir, quitar o eliminar no
  quedan archivos sueltos, y nada se borra antes de confirmar la transacción.
- Las pantallas: formulario de colecciones, panel, admin de Django y tienda.

Las reglas de validación de imágenes ya se prueban en `core/test_imagenes.py`;
aquí solo se comprueba que la portada las usa. Cada prueba escribe en un
`MEDIA_ROOT` temporal, nunca en `media/` del proyecto.
"""

import re
import shutil
import tempfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import ProtectedError
from django.db.models.signals import post_save
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from PIL import Image

from . import portadas
from .dashboard import (
    MENSAJE_ARCHIVO_CON_DIRECCION,
    MENSAJE_DIRECCION_CON_ARCHIVO,
    ColeccionForm,
)
from .imagenes import LADO_DETALLE_PX, MAX_BYTES_POR_IMAGEN
from .models import MENSAJE_PORTADA_DOBLE, Coleccion, Producto
from .test_galeria_vistas import crear_usuario
from .test_servicio_galeria import foto

URL_EXTERNA = "https://example.com/portada.jpg"
QUITAR = {"imagen-clear": "on"}  # la casilla «Quitar la portada actual»
RUTA_DE_PORTADA = re.compile(r"colecciones/[0-9a-f]{32}\.webp")
OTRO_COLOR = (10, 20, 30)


def datos(coleccion=None, **cambios):
    """Lo que envía el formulario; por defecto, los datos que ya tiene la colección."""
    campos = {
        "nombre": coleccion.nombre if coleccion else "Luz Dorada",
        "descripcion": coleccion.descripcion if coleccion else "",
        "temporada": coleccion.temporada if coleccion else "2026",
        "imagen_url": coleccion.imagen_url if coleccion else "",
        "activa": "on",
    }
    campos.update(cambios)
    return campos


def formulario(coleccion=None, archivo=None, **cambios):
    archivos = {"imagen": archivo} if archivo is not None else {}
    return ColeccionForm(datos(coleccion, **cambios), archivos, instance=coleccion)


def archivo_que_no_es_imagen():
    return SimpleUploadedFile("foto.jpg", b"esto no es una fotografia", content_type="image/jpeg")


def gif():
    salida = BytesIO()
    Image.new("RGB", (4, 4)).save(salida, format="GIF")
    return SimpleUploadedFile("foto.gif", salida.getvalue(), content_type="image/gif")


def media_temporal(prueba):
    """Pone `MEDIA_ROOT` en una carpeta temporal que se borra al terminar la prueba."""
    carpeta = tempfile.mkdtemp(prefix="portada-test-")
    prueba.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
    ajuste = override_settings(MEDIA_ROOT=carpeta)
    ajuste.enable()
    prueba.addCleanup(ajuste.disable)
    return Path(carpeta)


def archivos_en(media):
    """Todos los archivos del disco, con el nombre que les da Django (con «/»)."""
    return sorted(
        ruta.relative_to(media).as_posix() for ruta in media.rglob("*") if ruta.is_file()
    )


class _Base(TestCase):
    def setUp(self):
        super().setUp()
        self.media = media_temporal(self)

    def archivos(self):
        return archivos_en(self.media)

    def abrir(self, coleccion):
        """La portada guardada, ya leída (sin dejar el archivo abierto en el disco)."""
        with Image.open(self.media / coleccion.imagen.name) as imagen:
            imagen.load()
            return imagen.format, imagen.size, dict(imagen.getexif())

    def guardar(self, form):
        """Guarda como lo hace una vista: al volver, la transacción ya se confirmó."""
        self.assertTrue(form.is_valid(), form.errors.as_json())
        with self.captureOnCommitCallbacks(execute=True):
            return form.save()

    def con_portada(self, nombre="Luz Dorada", color=(200, 150, 50)):
        """Colección con una portada subida por el formulario."""
        return self.guardar(formulario(archivo=foto(color=color), nombre=nombre))

    def codigos(self, form, campo):
        return [error.code for error in form.errors.as_data().get(campo, [])]


# ---------------------------------------------------------------------------
# Subir la portada
# ---------------------------------------------------------------------------


class SubirPortadaTests(_Base):
    def test_guarda_una_sola_version_webp_en_la_carpeta_de_colecciones(self):
        coleccion = self.guardar(formulario(archivo=foto()))

        coleccion.refresh_from_db()
        self.assertTrue(RUTA_DE_PORTADA.fullmatch(coleccion.imagen.name), coleccion.imagen.name)
        self.assertEqual(self.archivos(), [coleccion.imagen.name])
        formato, _, _ = self.abrir(coleccion)
        self.assertEqual(formato, "WEBP")  # se subió un PNG: lo guardado es la versión procesada

    def test_una_imagen_grande_se_guarda_con_la_medida_de_la_tienda(self):
        grande = foto(tamano=(LADO_DETALLE_PX * 2, LADO_DETALLE_PX))

        coleccion = self.guardar(formulario(archivo=grande))

        _, medidas, _ = self.abrir(coleccion)
        self.assertEqual(medidas, (LADO_DETALLE_PX, LADO_DETALLE_PX // 2))

    def test_el_nombre_que_trae_el_archivo_nunca_llega_al_disco(self):
        self.guardar(formulario(archivo=foto("../../etc/passwd mía.png")))

        (nombre,) = self.archivos()
        self.assertTrue(RUTA_DE_PORTADA.fullmatch(nombre), nombre)

    def test_lo_guardado_no_lleva_los_metadatos_del_archivo_original(self):
        exif = Image.Exif()
        exif[0x010F] = "MarcaDeCamara"  # Make
        exif[0x8825] = {1: "N", 2: (4.0, 36.0, 0.0), 3: "W", 4: (74.0, 4.0, 0.0)}  # GPS
        salida = BytesIO()
        Image.new("RGB", (120, 160), (200, 150, 50)).save(salida, format="JPEG", exif=exif)
        self.assertIn(b"MarcaDeCamara", salida.getvalue())  # la entrada sí los traía
        original = SimpleUploadedFile("foto.jpg", salida.getvalue(), content_type="image/jpeg")

        coleccion = self.guardar(formulario(archivo=original))

        _, _, metadatos = self.abrir(coleccion)
        self.assertEqual(metadatos, {})
        self.assertNotIn(b"MarcaDeCamara", (self.media / coleccion.imagen.name).read_bytes())

    def test_rechaza_lo_mismo_que_las_fotografias_de_producto(self):
        pesada = foto().read() + b"0" * (MAX_BYTES_POR_IMAGEN + 1)
        casos = {
            "no_imagen": archivo_que_no_es_imagen(),
            "vacio": SimpleUploadedFile("foto.jpg", b"", content_type="image/jpeg"),
            "formato": gif(),
            "pesada": SimpleUploadedFile("foto.png", pesada, content_type="image/png"),
        }
        for codigo, archivo in casos.items():
            with self.subTest(codigo=codigo):
                form = formulario(archivo=archivo)

                self.assertFalse(form.is_valid())
                self.assertEqual(self.codigos(form, "imagen"), [codigo])

        self.assertFalse(Coleccion.objects.exists())
        self.assertEqual(self.archivos(), [])

    def test_un_archivo_rechazado_no_toca_la_portada_que_ya_habia(self):
        coleccion = self.con_portada()
        anterior = coleccion.imagen.name

        form = formulario(coleccion, archivo=archivo_que_no_es_imagen())

        self.assertFalse(form.is_valid())
        coleccion.refresh_from_db()
        self.assertEqual(coleccion.imagen.name, anterior)
        self.assertEqual(self.archivos(), [anterior])

    def test_la_portada_es_opcional(self):
        coleccion = self.guardar(formulario())

        self.assertFalse(coleccion.imagen)
        self.assertEqual(coleccion.imagen_url, "")
        self.assertEqual(self.archivos(), [])

    def test_guardar_otros_datos_conserva_la_portada(self):
        coleccion = self.con_portada()
        anterior = coleccion.imagen.name
        form = formulario(coleccion, temporada="2027")
        self.assertTrue(form.is_valid(), form.errors.as_json())

        with self.captureOnCommitCallbacks(execute=True) as pendientes:
            form.save()

        self.assertEqual(pendientes, [])  # no se programa ningún borrado
        coleccion.refresh_from_db()
        self.assertEqual((coleccion.temporada, coleccion.imagen.name), ("2027", anterior))
        self.assertEqual(self.archivos(), [anterior])

    def test_el_selector_propone_solo_los_formatos_admitidos(self):
        selector = str(ColeccionForm()["imagen"])

        self.assertIn('type="file"', selector)
        self.assertIn('accept="image/jpeg,image/png,image/webp"', selector)

    def test_si_otro_campo_falla_la_casilla_de_quitar_sigue_marcada(self):
        coleccion = self.con_portada()

        form = formulario(coleccion, nombre="", **QUITAR)

        self.assertFalse(form.is_valid())
        self.assertInHTML(
            '<input type="checkbox" name="imagen-clear" id="imagen-clear_id" checked>',
            str(form["imagen"]),
        )
        # Y sin haberla marcado, no aparece marcada.
        sin_tocar = Coleccion.objects.get(pk=coleccion.pk)
        self.assertInHTML(
            '<input type="checkbox" name="imagen-clear" id="imagen-clear_id">',
            str(formulario(sin_tocar, nombre="")["imagen"]),
        )


# ---------------------------------------------------------------------------
# Un archivo o una dirección, nunca los dos
# ---------------------------------------------------------------------------


class UnArchivoOUnaDireccionTests(_Base):
    def assertUnicoError(self, form, campo, mensaje):
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {campo: [mensaje]})

    def test_al_crear_no_admite_archivo_y_direccion_a_la_vez(self):
        form = formulario(archivo=foto(), imagen_url=URL_EXTERNA)

        self.assertUnicoError(form, "imagen", MENSAJE_ARCHIVO_CON_DIRECCION)
        self.assertFalse(Coleccion.objects.exists())
        self.assertEqual(self.archivos(), [])

    def test_con_portada_subida_no_admite_ademas_una_direccion(self):
        coleccion = self.con_portada()
        anterior = coleccion.imagen.name

        form = formulario(coleccion, imagen_url=URL_EXTERNA)

        self.assertUnicoError(form, "imagen_url", MENSAJE_DIRECCION_CON_ARCHIVO)
        coleccion.refresh_from_db()
        self.assertEqual((coleccion.imagen.name, coleccion.imagen_url), (anterior, ""))

    def test_con_direccion_guardada_no_admite_ademas_un_archivo(self):
        coleccion = Coleccion.objects.create(nombre="Luz Dorada", imagen_url=URL_EXTERNA)

        # La dirección sigue escrita en su casilla y además se elige un archivo.
        form = formulario(coleccion, archivo=foto())

        self.assertUnicoError(form, "imagen", MENSAJE_ARCHIVO_CON_DIRECCION)
        coleccion.refresh_from_db()
        self.assertFalse(coleccion.imagen)
        self.assertEqual(coleccion.imagen_url, URL_EXTERNA)
        self.assertEqual(self.archivos(), [])

    def test_cambiar_la_direccion_por_un_archivo(self):
        coleccion = Coleccion.objects.create(nombre="Luz Dorada", imagen_url=URL_EXTERNA)

        self.guardar(formulario(coleccion, archivo=foto(), imagen_url=""))

        coleccion.refresh_from_db()
        self.assertEqual(coleccion.imagen_url, "")
        self.assertEqual(self.archivos(), [coleccion.imagen.name])

    def test_cambiar_el_archivo_por_una_direccion_en_un_solo_envio(self):
        coleccion = self.con_portada()

        self.guardar(formulario(coleccion, imagen_url=URL_EXTERNA, **QUITAR))

        coleccion.refresh_from_db()
        self.assertFalse(coleccion.imagen)
        self.assertEqual(coleccion.imagen_url, URL_EXTERNA)
        self.assertEqual(self.archivos(), [])

    def test_no_se_puede_subir_y_quitar_en_el_mismo_envio(self):
        coleccion = self.con_portada()
        anterior = coleccion.imagen.name

        form = formulario(coleccion, archivo=foto(color=OTRO_COLOR), **QUITAR)

        self.assertFalse(form.is_valid())
        self.assertEqual(self.codigos(form, "imagen"), ["contradiction"])
        coleccion.refresh_from_db()
        self.assertEqual(coleccion.imagen.name, anterior)
        self.assertEqual(self.archivos(), [anterior])

    def test_el_modelo_rechaza_las_dos_portadas_a_la_vez(self):
        coleccion = Coleccion(
            nombre="Luz Dorada", imagen="colecciones/a.webp", imagen_url=URL_EXTERNA
        )

        with self.assertRaises(ValidationError) as ctx:
            coleccion.full_clean()

        self.assertEqual(ctx.exception.message_dict, {NON_FIELD_ERRORS: [MENSAJE_PORTADA_DOBLE]})

    def test_el_modelo_acepta_una_sola_portada_o_ninguna(self):
        for campos in ({}, {"imagen": "colecciones/a.webp"}, {"imagen_url": URL_EXTERNA}):
            with self.subTest(campos=campos):
                Coleccion(nombre="Luz Dorada", **campos).full_clean()  # no debe lanzar

    def test_una_direccion_en_blanco_no_cuenta_como_portada(self):
        coleccion = Coleccion(nombre="Luz Dorada", imagen="colecciones/a.webp", imagen_url="   ")

        coleccion.clean()  # no debe lanzar

        self.assertEqual(coleccion.imagen_url, "")

    def test_el_admin_de_django_tampoco_deja_guardar_las_dos(self):
        self.client.force_login(crear_usuario("administrador", "100000001", superusuario=True))
        coleccion = self.con_portada()

        respuesta = self.client.post(
            reverse("admin:core_coleccion_change", args=[coleccion.pk]),
            {**datos(coleccion, imagen_url=URL_EXTERNA), "_save": "Guardar"},
        )

        self.assertContains(respuesta, MENSAJE_PORTADA_DOBLE)
        coleccion.refresh_from_db()
        self.assertEqual(coleccion.imagen_url, "")

    def test_la_tienda_usa_el_archivo_y_si_no_hay_la_direccion(self):
        con_archivo = self.con_portada("Con archivo")
        con_direccion = Coleccion.objects.create(nombre="Con dirección", imagen_url=URL_EXTERNA)
        sin_portada = Coleccion.objects.create(nombre="Sin portada")
        # Datos anteriores a esta regla que tuvieran las dos: manda el archivo.
        con_las_dos = Coleccion(imagen="colecciones/a.webp", imagen_url=URL_EXTERNA)

        with self.assertNumQueries(0):
            self.assertEqual(con_archivo.imagen_catalogo, con_archivo.imagen.url)
            self.assertEqual(con_direccion.imagen_catalogo, URL_EXTERNA)
            self.assertEqual(sin_portada.imagen_catalogo, "")
            self.assertEqual(con_las_dos.imagen_catalogo, con_las_dos.imagen.url)
        self.assertTrue(con_archivo.imagen_catalogo.endswith(con_archivo.imagen.name))


# ---------------------------------------------------------------------------
# Los archivos en el disco al sustituir o quitar la portada
# ---------------------------------------------------------------------------


class ArchivosEnElDiscoTests(_Base):
    def setUp(self):
        super().setUp()
        self.coleccion = self.con_portada()
        self.anterior = self.coleccion.imagen.name
        self.assertEqual(self.archivos(), [self.anterior])

    def en_la_base(self):
        return Coleccion.objects.get(pk=self.coleccion.pk).imagen.name

    def test_al_subir_otra_fotografia_se_borra_la_anterior(self):
        self.guardar(formulario(self.coleccion, archivo=foto(color=OTRO_COLOR)))

        self.assertNotEqual(self.en_la_base(), self.anterior)
        self.assertEqual(self.archivos(), [self.en_la_base()])

    def test_la_anterior_no_se_borra_hasta_confirmar_la_transaccion(self):
        form = formulario(self.coleccion, archivo=foto(color=OTRO_COLOR))
        self.assertTrue(form.is_valid(), form.errors.as_json())

        with self.captureOnCommitCallbacks(execute=False) as pendientes:
            form.save()

        self.assertEqual(len(pendientes), 1)
        self.assertEqual(self.archivos(), sorted([self.anterior, self.en_la_base()]))

    def test_si_la_operacion_se_revierte_la_portada_anterior_sigue_en_su_sitio(self):
        form = formulario(self.coleccion, archivo=foto(color=OTRO_COLOR))
        self.assertTrue(form.is_valid(), form.errors.as_json())

        with self.captureOnCommitCallbacks(execute=True) as pendientes:
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    form.save()
                    raise RuntimeError("algo falló después de guardar")

        self.assertEqual(pendientes, [])
        self.assertEqual(self.en_la_base(), self.anterior)
        # Límite conocido (ver core/portadas.py): el archivo nuevo sí queda en el disco.
        self.assertIn(self.anterior, self.archivos())

    def test_al_quitar_la_portada_se_borra_su_archivo(self):
        self.guardar(formulario(self.coleccion, **QUITAR))

        self.assertEqual(self.en_la_base(), "")
        self.assertEqual(self.archivos(), [])

    def test_si_el_guardado_falla_el_archivo_nuevo_no_queda_en_el_disco(self):
        Coleccion.objects.create(nombre="Repetida")
        form = formulario(self.coleccion, archivo=foto(color=OTRO_COLOR))
        self.assertTrue(form.is_valid(), form.errors.as_json())
        coleccion = form.save(commit=False)
        coleccion.nombre = "Repetida"  # choca con el nombre único: la base lo rechaza

        with self.assertRaises(IntegrityError), transaction.atomic():
            coleccion.save()

        self.assertEqual(self.archivos(), [self.anterior])
        # El objeto vuelve a apuntar a la portada guardada: reintentar no deja una ruta rota.
        self.assertEqual(coleccion.imagen.name, self.anterior)
        self.assertEqual(self.en_la_base(), self.anterior)

    def test_si_falla_al_crear_tampoco_queda_el_archivo(self):
        form = formulario(archivo=foto(color=OTRO_COLOR), nombre="Otra")
        self.assertTrue(form.is_valid(), form.errors.as_json())
        nueva = form.save(commit=False)
        nueva.nombre = self.coleccion.nombre  # nombre repetido

        with self.assertRaises(IntegrityError), transaction.atomic():
            nueva.save()

        self.assertEqual(self.archivos(), [self.anterior])
        self.assertFalse(nueva.imagen)

    def test_no_borra_un_archivo_que_otra_coleccion_sigue_usando(self):
        gemela = Coleccion.objects.create(nombre="Gemela", imagen=self.anterior)

        self.guardar(formulario(self.coleccion, **QUITAR))

        self.assertEqual(self.en_la_base(), "")
        self.assertEqual(self.archivos(), [self.anterior])
        gemela.refresh_from_db()
        self.assertEqual(gemela.imagen.name, self.anterior)

    def test_nunca_borra_un_archivo_que_no_tenga_forma_de_portada(self):
        ajeno = default_storage.save("productos/7/foto.jpg", ContentFile(b"x"))
        rara = Coleccion.objects.create(nombre="Rara", imagen=ajeno)
        rara.imagen = ""

        with self.assertLogs("core.portadas", level="WARNING"):
            with self.captureOnCommitCallbacks(execute=True):
                rara.save()

        self.assertEqual(self.archivos(), sorted([self.anterior, ajeno]))

    def test_los_nombres_sospechosos_ni_siquiera_llegan_al_almacenamiento(self):
        almacenamiento = Coleccion._meta.get_field("imagen").storage
        sospechosos = (
            "productos/7/foto.jpg",
            "colecciones/sub/foto.webp",
            "colecciones/../secreto.txt",
            "../colecciones/a.webp",
            "/colecciones/a.webp",
            "colecciones/sin-extension",
            "colecciones/",
        )

        with mock.patch.object(almacenamiento, "delete") as borrar:
            for nombre in sospechosos:
                with self.subTest(nombre=nombre):
                    with self.assertLogs("core.portadas", level="WARNING"):
                        self.assertFalse(portadas.borrar_si_nadie_la_usa(Coleccion, nombre))

        borrar.assert_not_called()

    def test_un_fallo_del_almacenamiento_al_borrar_no_impide_guardar(self):
        almacenamiento = Coleccion._meta.get_field("imagen").storage
        form = formulario(self.coleccion, **QUITAR)
        self.assertTrue(form.is_valid(), form.errors.as_json())

        with mock.patch.object(almacenamiento, "delete", side_effect=OSError("disco ocupado")):
            with self.assertLogs("core.portadas", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    form.save()  # no debe lanzar

        self.assertEqual(self.en_la_base(), "")
        self.assertEqual(self.archivos(), [self.anterior])  # queda suelto, pero se guardó

    def test_si_no_se_puede_comprobar_el_uso_el_archivo_no_se_borra(self):
        sin_conexion = DatabaseError("sin conexión")

        with mock.patch.object(Coleccion.objects, "filter", side_effect=sin_conexion):
            with self.assertLogs("core.portadas", level="ERROR"):
                borrado = portadas.borrar_si_nadie_la_usa(Coleccion, self.anterior)  # no lanza

        self.assertFalse(borrado)
        self.assertEqual(self.archivos(), [self.anterior])  # ante la duda, se conserva

    def test_guardar_solo_otros_campos_no_borra_la_portada(self):
        self.coleccion.imagen = ""  # cambio en memoria que NO se guarda
        self.coleccion.temporada = "2027"

        with self.captureOnCommitCallbacks(execute=True):
            self.coleccion.save(update_fields=["temporada"])

        self.assertEqual(self.en_la_base(), self.anterior)
        self.assertEqual(self.archivos(), [self.anterior])

    def test_tambien_cuida_el_archivo_cuando_se_guarda_sin_formulario(self):
        self.coleccion.imagen = ContentFile(b"otra portada", name="otra.webp")

        with self.captureOnCommitCallbacks(execute=True):
            self.coleccion.save()

        self.assertNotEqual(self.en_la_base(), self.anterior)
        self.assertEqual(self.archivos(), [self.en_la_base()])


# ---------------------------------------------------------------------------
# Los archivos en el disco al eliminar una colección
# ---------------------------------------------------------------------------


class EliminarColeccionTests(_Base):
    def setUp(self):
        super().setUp()
        self.coleccion = self.con_portada()
        self.coleccion_id = self.coleccion.pk  # delete() lo borra del objeto en memoria
        self.otra = self.con_portada("Otra", color=OTRO_COLOR)
        self.assertEqual(len(self.archivos()), 2)

    def iniciar_sesion(self):
        self.client.force_login(crear_usuario("administrador", "100000001", superusuario=True))

    def assertSoloQuedaLaOtra(self):
        self.assertFalse(Coleccion.objects.filter(pk=self.coleccion_id).exists())
        self.assertEqual(self.archivos(), [self.otra.imagen.name])

    def assertNoSeBorroNada(self):
        self.assertTrue(Coleccion.objects.filter(pk=self.coleccion_id).exists())
        self.assertEqual(len(self.archivos()), 2)

    def test_borrar_el_objeto_borra_su_archivo(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.coleccion.delete()

        self.assertSoloQuedaLaOtra()

    def test_borrar_en_bloque_tambien_limpia(self):
        with self.captureOnCommitCallbacks(execute=True):
            Coleccion.objects.filter(pk=self.coleccion_id).delete()

        self.assertSoloQuedaLaOtra()

    def test_el_archivo_no_se_toca_hasta_confirmar_la_transaccion(self):
        with self.captureOnCommitCallbacks(execute=False) as pendientes:
            self.coleccion.delete()

        self.assertEqual(len(pendientes), 1)
        self.assertEqual(len(self.archivos()), 2)

    def test_si_el_borrado_se_revierte_el_archivo_sigue_ahi(self):
        with self.captureOnCommitCallbacks(execute=True) as pendientes:
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    self.coleccion.delete()
                    raise RuntimeError("algo falló después de borrar")

        self.assertEqual(pendientes, [])
        self.assertNoSeBorroNada()

    def test_una_coleccion_con_productos_no_se_elimina_y_conserva_su_portada(self):
        Producto.objects.create(
            coleccion=self.coleccion, nombre="Anillo Aurora", precio=Decimal("1000000.00")
        )

        with self.captureOnCommitCallbacks(execute=True) as pendientes:
            with self.assertRaises(ProtectedError):
                self.coleccion.delete()

        self.assertEqual(pendientes, [])
        self.assertNoSeBorroNada()

    def test_una_coleccion_sin_portada_se_elimina_sin_programar_nada(self):
        sin_portada = Coleccion.objects.create(nombre="Sin portada")

        with self.captureOnCommitCallbacks(execute=True) as pendientes:
            sin_portada.delete()

        self.assertEqual(pendientes, [])
        self.assertEqual(len(self.archivos()), 2)

    def test_eliminar_desde_la_pantalla_de_colecciones(self):
        self.iniciar_sesion()

        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(
                reverse("core:coleccion_eliminar", args=[self.coleccion_id])
            )

        self.assertEqual(respuesta.status_code, 302)
        self.assertSoloQuedaLaOtra()

    def test_eliminar_desde_el_panel(self):
        self.iniciar_sesion()

        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(
                reverse("core:admin_section", kwargs={"seccion": "colecciones"}),
                {"recurso": "colecciones", "accion": "delete", "registro": self.coleccion_id},
            )

        self.assertEqual(respuesta.status_code, 302)
        self.assertSoloQuedaLaOtra()

    def test_eliminar_desde_el_admin_de_django(self):
        self.iniciar_sesion()

        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(
                reverse("admin:core_coleccion_delete", args=[self.coleccion_id]),
                {"post": "yes"},
            )

        self.assertEqual(respuesta.status_code, 302)
        self.assertSoloQuedaLaOtra()


# ---------------------------------------------------------------------------
# Sin una transacción abierta, que es como guardan las vistas
# ---------------------------------------------------------------------------


class SinTransaccionAbiertaTests(TransactionTestCase):
    """Aquí cada guardado se confirma en el momento, igual que en las vistas.

    (En las demás clases cada prueba corre dentro de una transacción.)
    """

    def setUp(self):
        super().setUp()
        self.media = media_temporal(self)

    def archivos(self):
        return archivos_en(self.media)

    def guardar(self, form):
        self.assertTrue(form.is_valid(), form.errors.as_json())
        return form.save()

    def test_al_sustituir_la_anterior_se_borra_en_el_momento(self):
        coleccion = self.guardar(formulario(archivo=foto()))
        anterior = coleccion.imagen.name

        self.guardar(formulario(coleccion, archivo=foto(color=OTRO_COLOR)))

        guardada = Coleccion.objects.get(pk=coleccion.pk).imagen.name
        self.assertNotEqual(guardada, anterior)
        self.assertEqual(self.archivos(), [guardada])

    def test_al_eliminar_la_coleccion_su_archivo_se_borra_en_el_momento(self):
        coleccion = self.guardar(formulario(archivo=foto()))

        coleccion.delete()

        self.assertEqual(self.archivos(), [])

    def test_si_el_guardado_falla_el_archivo_nuevo_no_queda_en_el_disco(self):
        Coleccion.objects.create(nombre="Repetida")
        form = formulario(archivo=foto(), nombre="Otra")
        self.assertTrue(form.is_valid(), form.errors.as_json())
        nueva = form.save(commit=False)
        nueva.nombre = "Repetida"  # choca con el nombre único: la base lo rechaza

        with self.assertRaises(IntegrityError):
            nueva.save()

        self.assertEqual(self.archivos(), [])
        self.assertFalse(nueva.imagen)
        self.assertEqual(Coleccion.objects.count(), 1)

    def test_si_algo_falla_despues_de_guardar_la_fila_el_archivo_se_conserva(self):
        def receptor_que_falla(**kwargs):
            raise RuntimeError("falló después de guardar")

        post_save.connect(receptor_que_falla, sender=Coleccion)
        self.addCleanup(post_save.disconnect, receptor_que_falla, sender=Coleccion)
        form = formulario(archivo=foto())
        self.assertTrue(form.is_valid(), form.errors.as_json())

        with self.assertRaises(RuntimeError):
            form.save()

        # La fila quedó guardada con su portada: borrar el archivo la dejaría rota.
        guardada = Coleccion.objects.get().imagen.name
        self.assertEqual(self.archivos(), [guardada])


# ---------------------------------------------------------------------------
# Las pantallas
# ---------------------------------------------------------------------------


def con_permisos_de_coleccion(usuario, *claves):
    tipo = ContentType.objects.get_for_model(Coleccion)
    for clave in claves:
        usuario.user_permissions.add(Permission.objects.get(codename=clave, content_type=tipo))
    return get_user_model().objects.get(pk=usuario.pk)  # sin la caché de permisos


class _BasePantallas(_Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(crear_usuario("administrador", "100000001", superusuario=True))

    def enviar(self, url, campos):
        """Envía el formulario; al volver, la transacción ya se confirmó."""
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url, campos)


class FormularioDeColeccionesTests(_BasePantallas):
    def setUp(self):
        super().setUp()
        self.url_crear = reverse("core:coleccion_crear")
        self.url_lista = reverse("core:coleccion_listar")

    def url_editar(self, coleccion):
        return reverse("core:coleccion_editar", args=[coleccion.pk])

    def test_el_formulario_puede_enviar_archivos(self):
        respuesta = self.client.get(self.url_crear)

        self.assertContains(respuesta, 'enctype="multipart/form-data"')
        self.assertContains(respuesta, '<input type="file" name="imagen"')
        self.assertContains(respuesta, "css/portada-campo.css")
        self.assertNotContains(respuesta, 'name="imagen-clear"')  # no hay nada que quitar

    def test_la_ayuda_queda_asociada_a_su_campo(self):
        respuesta = self.client.get(self.url_crear)

        self.assertContains(respuesta, 'aria-describedby="id_imagen_helptext"')
        self.assertContains(respuesta, 'id="id_imagen_helptext"')

    def test_al_editar_muestra_la_portada_actual_y_permite_quitarla(self):
        coleccion = self.con_portada()

        respuesta = self.client.get(self.url_editar(coleccion))

        self.assertContains(respuesta, f'<img src="{coleccion.imagen.url}"')
        self.assertContains(
            respuesta, '<input type="checkbox" name="imagen-clear" id="imagen-clear_id">', html=True
        )
        self.assertContains(respuesta, "Quitar la portada actual")

    def test_crear_con_portada(self):
        respuesta = self.enviar(self.url_crear, {**datos(), "imagen": foto()})

        self.assertRedirects(respuesta, self.url_lista)
        coleccion = Coleccion.objects.get(nombre="Luz Dorada")
        self.assertEqual(self.archivos(), [coleccion.imagen.name])

    def test_sustituir_la_portada(self):
        coleccion = self.con_portada()
        anterior = coleccion.imagen.name

        respuesta = self.enviar(
            self.url_editar(coleccion), {**datos(coleccion), "imagen": foto(color=OTRO_COLOR)}
        )

        self.assertRedirects(respuesta, self.url_lista)
        coleccion.refresh_from_db()
        self.assertNotEqual(coleccion.imagen.name, anterior)
        self.assertEqual(self.archivos(), [coleccion.imagen.name])

    def test_quitar_la_portada(self):
        coleccion = self.con_portada()

        respuesta = self.enviar(self.url_editar(coleccion), datos(coleccion, **QUITAR))

        self.assertRedirects(respuesta, self.url_lista)
        coleccion.refresh_from_db()
        self.assertFalse(coleccion.imagen)
        self.assertEqual(self.archivos(), [])

    def test_un_archivo_que_no_es_una_imagen_se_rechaza_con_su_motivo(self):
        respuesta = self.enviar(self.url_crear, {**datos(), "imagen": archivo_que_no_es_imagen()})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "No pudimos reconocer el archivo como una imagen")
        self.assertFalse(Coleccion.objects.exists())
        self.assertEqual(self.archivos(), [])

    def test_archivo_y_direccion_a_la_vez_se_rechaza_con_su_motivo(self):
        respuesta = self.enviar(
            self.url_crear, {**datos(imagen_url=URL_EXTERNA), "imagen": foto()}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, MENSAJE_ARCHIVO_CON_DIRECCION)
        self.assertFalse(Coleccion.objects.exists())
        self.assertEqual(self.archivos(), [])

    def test_sin_permiso_para_editar_no_se_guarda_ningun_archivo(self):
        coleccion = Coleccion.objects.create(nombre="Luz Dorada")
        solo_lectura = con_permisos_de_coleccion(
            crear_usuario("lectura", "100000002", personal=True), "view_coleccion"
        )
        self.client.force_login(solo_lectura)

        respuesta = self.enviar(self.url_editar(coleccion), {**datos(coleccion), "imagen": foto()})

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self.archivos(), [])


class PanelTests(_BasePantallas):
    def setUp(self):
        super().setUp()
        self.url = reverse("core:admin_section", kwargs={"seccion": "colecciones"})

    def crear(self, **campos):
        """Envío del formulario «Crear nuevo» del panel."""
        envio = {"recurso": "colecciones", "accion": "create"}
        envio.update({f"colecciones-nuevo-{clave}": valor for clave, valor in campos.items()})
        return self.enviar(self.url, envio)

    def editar(self, coleccion, **campos):
        """Envío del formulario de edición (el diálogo) de una colección."""
        envio = {"recurso": "colecciones", "accion": "edit", "registro": coleccion.pk}
        envio.update(
            {f"colecciones-{coleccion.pk}-{clave}": valor for clave, valor in campos.items()}
        )
        return self.enviar(self.url, envio)

    def test_el_panel_ofrece_subir_la_portada_al_crear_y_al_editar(self):
        coleccion = self.con_portada()

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, '<input type="file" name="colecciones-nuevo-imagen"')
        self.assertContains(
            respuesta, f'<input type="file" name="colecciones-{coleccion.pk}-imagen"'
        )
        self.assertContains(respuesta, f'<img src="{coleccion.imagen.url}"')
        self.assertContains(respuesta, f'name="colecciones-{coleccion.pk}-imagen-clear"')
        self.assertContains(respuesta, 'id="id_colecciones-nuevo-imagen_helptext"')

    def test_la_hoja_de_estilos_solo_se_carga_en_colecciones(self):
        self.assertContains(self.client.get(self.url), "css/portada-campo.css")

        otra = self.client.get(reverse("core:admin_section", kwargs={"seccion": "productos"}))

        self.assertNotContains(otra, "css/portada-campo.css")

    def test_crear_con_portada(self):
        respuesta = self.crear(**datos(), imagen=foto())

        self.assertEqual(respuesta.status_code, 302)
        coleccion = Coleccion.objects.get(nombre="Luz Dorada")
        self.assertEqual(self.archivos(), [coleccion.imagen.name])

    def test_sustituir_la_portada(self):
        coleccion = self.con_portada()
        anterior = coleccion.imagen.name

        respuesta = self.editar(coleccion, **datos(coleccion), imagen=foto(color=OTRO_COLOR))

        self.assertEqual(respuesta.status_code, 302)
        coleccion.refresh_from_db()
        self.assertNotEqual(coleccion.imagen.name, anterior)
        self.assertEqual(self.archivos(), [coleccion.imagen.name])

    def test_quitar_la_portada(self):
        coleccion = self.con_portada()

        respuesta = self.editar(coleccion, **datos(coleccion, **QUITAR))

        self.assertEqual(respuesta.status_code, 302)
        coleccion.refresh_from_db()
        self.assertFalse(coleccion.imagen)
        self.assertEqual(self.archivos(), [])

    def test_un_error_en_la_portada_reabre_la_ficha_con_el_motivo(self):
        coleccion = self.con_portada()
        anterior = coleccion.imagen.name

        respuesta = self.editar(coleccion, **datos(coleccion, imagen_url=URL_EXTERNA))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, MENSAJE_DIRECCION_CON_ARCHIVO)
        self.assertContains(respuesta, "data-dashboard-dialog-autoshow")
        coleccion.refresh_from_db()
        self.assertEqual((coleccion.imagen.name, coleccion.imagen_url), (anterior, ""))

    def test_un_archivo_invalido_al_crear_se_rechaza_con_su_motivo(self):
        respuesta = self.crear(**datos(), imagen=archivo_que_no_es_imagen())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "No pudimos reconocer el archivo como una imagen")
        self.assertFalse(Coleccion.objects.exists())
        self.assertEqual(self.archivos(), [])

    def test_sin_permiso_para_editar_no_se_guarda_ningun_archivo(self):
        coleccion = Coleccion.objects.create(nombre="Luz Dorada")
        solo_lectura = con_permisos_de_coleccion(
            crear_usuario("lectura", "100000002", personal=True), "view_coleccion"
        )
        self.client.force_login(solo_lectura)

        respuesta = self.editar(coleccion, **datos(coleccion), imagen=foto())

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self.archivos(), [])


class TiendaTests(_Base):
    def test_la_tarjeta_usa_la_portada_subida(self):
        coleccion = self.con_portada("Alma Dorada")

        respuesta = self.client.get(reverse("core:inicio"))

        self.assertContains(respuesta, f'<img src="{coleccion.imagen.url}"')

    def test_la_tarjeta_sigue_usando_la_direccion_si_no_hay_archivo(self):
        Coleccion.objects.create(nombre="Alma Dorada", imagen_url=URL_EXTERNA)

        respuesta = self.client.get(reverse("core:inicio"))

        self.assertContains(respuesta, f'<img src="{URL_EXTERNA}"')

    def test_sin_portada_propia_se_ve_la_imagen_de_siempre(self):
        Coleccion.objects.create(nombre="Luna de Miel")

        respuesta = self.client.get(reverse("core:inicio"))

        self.assertContains(respuesta, "img/coleccion-lunademiel.webp")
        self.assertNotContains(respuesta, "/media/colecciones/")

    def test_al_quitar_la_portada_la_tienda_vuelve_a_la_imagen_de_siempre(self):
        coleccion = self.con_portada("Luna de Miel")
        self.guardar(formulario(coleccion, **QUITAR))

        respuesta = self.client.get(reverse("core:inicio"))

        self.assertContains(respuesta, "img/coleccion-lunademiel.webp")
        self.assertNotContains(respuesta, "/media/colecciones/")
