"""Al eliminar un producto se limpian sus archivos (carpeta `productos/<id>/`).

Django borra las filas de `ProductoImagen` en cascada, pero no los archivos.
La limpieza la dispara `core/signals.py` y la ejecuta
`servicio_galeria.borrar_carpeta_de_producto`, siempre después de confirmar la
transacción. Cada prueba usa un `MEDIA_ROOT` temporal (ver `_Base`).

También se comprueba qué pasa cuando la limpieza solo puede hacerse a medias
(un archivo en uso, una carpeta sin permiso): se borra lo que se puede, queda
anotado en el registro, el producto se elimina igual y un reintento posterior
termina el trabajo.
"""

import shutil
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from . import servicio_galeria as galeria
from .models import Producto, ProductoImagen
from .test_servicio_galeria import _Base, crear_producto, foto, fotos


def crear_superusuario():
    return get_user_model().objects.create_superuser(
        username="administrador",
        password="clave-de-prueba",
        first_name="Admin",
        last_name="Prueba",
        tipo_documento="CC",
        documento="123456789",
        fecha_nacimiento=date(1990, 1, 1),
        telefono="3001234567",
    )


class BorrarCarpetaDeProductoTests(_Base):
    def carpeta(self, producto=None):
        return self.media / "productos" / str((producto or self.producto).pk)

    def test_borra_originales_derivados_y_las_carpetas(self):
        galeria.agregar_archivos(self.producto, fotos(2))
        self.assertEqual(len(self.archivos_en_disco()), 6)

        galeria.borrar_carpeta_de_producto(self.producto.pk)

        self.assertEqual(self.archivos_en_disco(), [])
        self.assertFalse(self.carpeta().exists())

    def test_no_toca_la_carpeta_de_otro_producto(self):
        otro = crear_producto("Anillo Brisa")
        galeria.agregar_archivos(self.producto, [foto()])
        galeria.agregar_archivos(otro, [foto()])

        galeria.borrar_carpeta_de_producto(self.producto.pk)

        self.assertFalse(self.carpeta().exists())
        self.assertEqual(len(self.archivos_en_disco()), 3)
        for ruta in self.archivos_en_disco():
            self.assertIn(self.carpeta(otro), ruta.parents)

    def test_un_id_que_empieza_igual_no_se_confunde(self):
        # «productos/1» no debe arrastrar «productos/10» ni «productos/11».
        for carpeta in ("1", "10", "11"):
            default_storage.save(f"productos/{carpeta}/a.jpg", ContentFile(b"x"))
            default_storage.save(f"productos/{carpeta}/derivados/a.webp", ContentFile(b"x"))

        galeria.borrar_carpeta_de_producto(1)

        self.assertFalse((self.media / "productos" / "1").exists())
        self.assertEqual(len(self.archivos_en_disco()), 4)

    def test_sin_carpeta_no_falla(self):
        galeria.borrar_carpeta_de_producto(self.producto.pk)  # no debe lanzar

        self.assertEqual(self.archivos_en_disco(), [])

    def test_conserva_una_subcarpeta_que_no_es_del_servicio(self):
        galeria.agregar_archivos(self.producto, [foto()])
        ajeno = default_storage.save(
            f"productos/{self.producto.pk}/respaldo/nota.txt", ContentFile(b"x")
        )

        with self.assertLogs("core.servicio_galeria", level="WARNING"):
            galeria.borrar_carpeta_de_producto(self.producto.pk)

        self.assertEqual(self.archivos_en_disco(), [self.media / ajeno])

    def test_un_identificador_que_no_es_un_numero_no_borra_nada(self):
        galeria.agregar_archivos(self.producto, [foto()])

        for invalido in (None, "", "../..", f"{self.producto.pk}/../..", "abc"):
            with self.subTest(invalido=invalido):
                with self.assertLogs("core.servicio_galeria", level="WARNING"):
                    galeria.borrar_carpeta_de_producto(invalido)

        self.assertEqual(len(self.archivos_en_disco()), 3)

    def test_un_fallo_del_almacenamiento_no_se_propaga(self):
        galeria.agregar_archivos(self.producto, [foto()])
        almacenamiento = ProductoImagen._meta.get_field("archivo").storage

        with mock.patch.object(almacenamiento, "delete", side_effect=OSError("disco lleno")):
            with self.assertLogs("core.servicio_galeria", level="WARNING"):
                galeria.borrar_carpeta_de_producto(self.producto.pk)  # no debe lanzar

        self.assertEqual(len(self.archivos_en_disco()), 3)


class EliminarProductoLimpiaArchivosTests(_Base):
    def setUp(self):
        super().setUp()
        galeria.agregar_archivos(self.producto, fotos(2))
        self.producto_id = self.producto.pk  # delete() lo borra del objeto en memoria
        self.otro = crear_producto("Anillo Brisa")
        galeria.agregar_archivos(self.otro, [foto()])
        self.assertEqual(len(self.archivos_en_disco()), 9)

    def assertSoloQuedaElOtro(self):
        self.assertFalse(Producto.objects.filter(pk=self.producto_id).exists())
        self.assertFalse(ProductoImagen.objects.filter(producto_id=self.producto_id).exists())
        restantes = self.archivos_en_disco()
        self.assertEqual(len(restantes), 3)
        carpeta_del_otro = self.media / "productos" / str(self.otro.pk)
        for ruta in restantes:
            self.assertIn(carpeta_del_otro, ruta.parents)

    def test_borrar_el_objeto_limpia_su_carpeta(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.producto.delete()

        self.assertSoloQuedaElOtro()

    def test_borrar_en_bloque_tambien_limpia(self):
        with self.captureOnCommitCallbacks(execute=True):
            Producto.objects.filter(pk=self.producto_id).delete()

        self.assertSoloQuedaElOtro()

    def test_los_archivos_no_se_tocan_hasta_confirmar_la_transaccion(self):
        with self.captureOnCommitCallbacks(execute=False) as pendientes:
            self.producto.delete()

        self.assertEqual(len(pendientes), 1)
        self.assertEqual(len(self.archivos_en_disco()), 9)

    def test_si_el_borrado_se_revierte_las_fotografias_siguen_ahi(self):
        producto_id = self.producto.pk  # delete() lo borra del objeto en memoria

        with self.captureOnCommitCallbacks(execute=True) as pendientes:
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    self.producto.delete()
                    raise RuntimeError("algo falló después de borrar")

        self.assertEqual(pendientes, [])
        self.assertTrue(Producto.objects.filter(pk=producto_id).exists())
        self.assertEqual(ProductoImagen.objects.filter(producto_id=producto_id).count(), 2)
        self.assertEqual(len(self.archivos_en_disco()), 9)

    def test_eliminar_desde_la_vista_de_productos(self):
        self.client.force_login(crear_superusuario())

        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(
                reverse("core:producto_eliminar", args=[self.producto_id])
            )

        self.assertEqual(respuesta.status_code, 302)
        self.assertSoloQuedaElOtro()

    def test_eliminar_desde_el_panel(self):
        self.client.force_login(crear_superusuario())

        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(
                reverse("core:admin_section", kwargs={"seccion": "productos"}),
                {"recurso": "productos", "accion": "delete", "registro": self.producto_id},
            )

        self.assertEqual(respuesta.status_code, 302)
        self.assertSoloQuedaElOtro()

    def test_eliminar_desde_el_admin_de_django(self):
        self.client.force_login(crear_superusuario())

        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(
                reverse("admin:core_producto_delete", args=[self.producto_id]),
                {"post": "yes"},
            )

        self.assertEqual(respuesta.status_code, 302)
        self.assertSoloQuedaElOtro()


# ---------------------------------------------------------------------------
# Fallos parciales: la limpieza solo puede hacerse a medias
# ---------------------------------------------------------------------------


def borrado_que_falla_con(almacenamiento, condicion):
    """Sustituye `almacenamiento.delete`: falla solo con los nombres que cumplen `condicion`.

    Imita un archivo que el sistema no deja borrar (en Windows, por ejemplo,
    uno que otro programa tiene abierto). Con el resto borra de verdad.
    """
    borrar_de_verdad = almacenamiento.delete

    def borrar(nombre):
        if condicion(nombre):
            raise PermissionError(13, "El archivo está en uso", nombre)
        return borrar_de_verdad(nombre)

    return mock.patch.object(almacenamiento, "delete", side_effect=borrar)


class FallosParcialesTests(_Base):
    def setUp(self):
        super().setUp()
        galeria.agregar_archivos(self.producto, fotos(2))
        self.primera, self.segunda = self.filas()
        self.producto_id = self.producto.pk  # delete() lo borra del objeto en memoria
        self.almacenamiento = ProductoImagen._meta.get_field("archivo").storage
        self.assertEqual(len(self.nombres_en_disco()), 6)

    def nombres_en_disco(self):
        return sorted(
            ruta.relative_to(self.media).as_posix() for ruta in self.archivos_en_disco()
        )

    def limpiar_fallando_con(self, condicion):
        """Limpia la carpeta con archivos que no se dejan borrar; devuelve (resultado, registro)."""
        with borrado_que_falla_con(self.almacenamiento, condicion):
            with self.assertLogs("core.servicio_galeria", level="ERROR") as registro:
                resultado = galeria.borrar_carpeta_de_producto(self.producto_id)  # no lanza
        return resultado, "\n".join(registro.output)

    def test_un_archivo_que_no_se_deja_borrar_no_impide_borrar_los_demas(self):
        # Falla el PRIMERO que la limpieza va a encontrar: los siguientes se
        # tienen que borrar igualmente.
        carpeta = f"productos/{self.producto_id}"
        _, originales = self.almacenamiento.listdir(carpeta)
        en_uso = f"{carpeta}/{originales[0]}"

        limpia, registro = self.limpiar_fallando_con(lambda nombre: nombre == en_uso)

        self.assertFalse(limpia)
        self.assertEqual(self.nombres_en_disco(), [en_uso])
        # El registro dice qué archivo quedó y cómo reintentarlo.
        self.assertIn(en_uso, registro)
        self.assertIn(f"borrar_carpeta_de_producto({self.producto_id})", registro)

    def test_un_reintento_posterior_termina_la_limpieza(self):
        en_uso = self.segunda.archivo_miniatura.name
        self.limpiar_fallando_con(lambda nombre: nombre == en_uso)
        self.assertEqual(self.nombres_en_disco(), [en_uso])

        limpia = galeria.borrar_carpeta_de_producto(self.producto_id)  # ya sin el fallo

        self.assertTrue(limpia)
        self.assertEqual(self.nombres_en_disco(), [])
        self.assertFalse((self.media / "productos" / str(self.producto_id)).exists())

    def test_un_fallo_en_los_derivados_no_impide_borrar_los_originales(self):
        limpia, _ = self.limpiar_fallando_con(lambda nombre: "/derivados/" in nombre)

        self.assertFalse(limpia)
        self.assertEqual(
            self.nombres_en_disco(),
            sorted(
                campo.name
                for fila in (self.primera, self.segunda)
                for campo in (fila.archivo_detalle, fila.archivo_miniatura)
            ),
        )

    def test_un_fallo_en_los_originales_no_impide_borrar_los_derivados(self):
        originales = {self.primera.archivo.name, self.segunda.archivo.name}

        limpia, _ = self.limpiar_fallando_con(lambda nombre: nombre in originales)

        self.assertFalse(limpia)
        self.assertEqual(self.nombres_en_disco(), sorted(originales))
        self.assertFalse(
            (self.media / "productos" / str(self.producto_id) / "derivados").exists()
        )

    def test_si_una_carpeta_no_se_puede_leer_no_se_propaga_ni_se_da_por_limpia(self):
        with mock.patch.object(
            self.almacenamiento, "listdir", side_effect=PermissionError(13, "Sin permiso")
        ):
            with self.assertLogs("core.servicio_galeria", level="ERROR"):
                limpia = galeria.borrar_carpeta_de_producto(self.producto_id)  # no lanza

        self.assertFalse(limpia)
        self.assertEqual(len(self.nombres_en_disco()), 6)

    def test_sin_fallos_la_carpeta_queda_limpia(self):
        self.assertTrue(galeria.borrar_carpeta_de_producto(self.producto_id))
        self.assertTrue(galeria.borrar_carpeta_de_producto(self.producto_id))  # ya no existe

    def test_el_producto_se_elimina_aunque_la_limpieza_quede_a_medias(self):
        en_uso = self.primera.archivo_detalle.name

        with borrado_que_falla_con(self.almacenamiento, lambda nombre: nombre == en_uso):
            with self.assertLogs("core.servicio_galeria", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    self.producto.delete()  # no lanza

        self.assertFalse(Producto.objects.filter(pk=self.producto_id).exists())
        self.assertFalse(ProductoImagen.objects.filter(producto_id=self.producto_id).exists())
        self.assertEqual(self.nombres_en_disco(), [en_uso])

    def test_al_eliminar_una_fotografia_la_fila_se_borra_aunque_un_archivo_no_se_deje(self):
        en_uso = self.primera.archivo_detalle.name

        with borrado_que_falla_con(self.almacenamiento, lambda nombre: nombre == en_uso):
            with self.assertLogs("core.servicio_galeria", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    galeria.eliminar_imagen(self.producto, self.primera.pk)  # no lanza

        self.assertEqual(self.filas(), [self.segunda])
        self.assertGaleriaConsistente()
        de_la_segunda = [
            campo.name
            for campo in (
                self.segunda.archivo,
                self.segunda.archivo_detalle,
                self.segunda.archivo_miniatura,
            )
        ]
        self.assertEqual(self.nombres_en_disco(), sorted([en_uso, *de_la_segunda]))

    def test_eliminar_el_producto_recoge_lo_que_dejo_un_fallo_anterior(self):
        en_uso = self.primera.archivo_detalle.name
        with borrado_que_falla_con(self.almacenamiento, lambda nombre: nombre == en_uso):
            with self.assertLogs("core.servicio_galeria", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    galeria.eliminar_imagen(self.producto, self.primera.pk)
        self.assertIn(en_uso, self.nombres_en_disco())  # quedó suelto, sin fila

        with self.captureOnCommitCallbacks(execute=True):
            self.producto.delete()

        self.assertEqual(self.nombres_en_disco(), [])


class ConfirmacionRealTests(TransactionTestCase):
    """Sin `captureOnCommitCallbacks`: cada operación se confirma de verdad.

    Es como eliminan las vistas. Aquí se ve que un fallo de la limpieza —incluso
    uno que nadie previó— no llega a quien elimina el producto.
    """

    def setUp(self):
        super().setUp()
        carpeta = tempfile.mkdtemp(prefix="limpieza-test-")
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=carpeta)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.media = Path(carpeta)
        self.producto = crear_producto()
        galeria.agregar_archivos(self.producto, [foto()])
        self.producto_id = self.producto.pk

    def archivos(self):
        return sorted(ruta for ruta in self.media.rglob("*") if ruta.is_file())

    def test_al_eliminar_el_producto_su_carpeta_se_borra_en_el_momento(self):
        self.assertEqual(len(self.archivos()), 3)

        self.producto.delete()

        self.assertEqual(self.archivos(), [])

    def test_un_error_inesperado_de_la_limpieza_no_llega_a_quien_elimina(self):
        inesperado = RuntimeError("el almacenamiento respondió algo que nadie previó")

        with mock.patch.object(galeria, "borrar_carpeta_de_producto", side_effect=inesperado):
            with self.assertLogs("django.db.backends.base", level="ERROR"):
                self.producto.delete()  # no lanza

        self.assertFalse(Producto.objects.filter(pk=self.producto_id).exists())
        self.assertEqual(len(self.archivos()), 3)  # siguen ahí...
        self.assertTrue(galeria.borrar_carpeta_de_producto(self.producto_id))  # ...y se reintenta
        self.assertEqual(self.archivos(), [])

    def test_la_pantalla_responde_bien_aunque_la_limpieza_falle(self):
        self.client.force_login(crear_superusuario())
        inesperado = RuntimeError("el almacenamiento respondió algo que nadie previó")

        with mock.patch.object(galeria, "borrar_carpeta_de_producto", side_effect=inesperado):
            with self.assertLogs("django.db.backends.base", level="ERROR"):
                respuesta = self.client.post(
                    reverse("core:producto_eliminar", args=[self.producto_id])
                )

        self.assertEqual(respuesta.status_code, 302)  # y no un error 500
        self.assertFalse(Producto.objects.filter(pk=self.producto_id).exists())

    def test_eliminar_una_fotografia_tampoco_falla_por_un_error_inesperado(self):
        (imagen,) = galeria.listar(self.producto)
        inesperado = RuntimeError("el almacenamiento respondió algo que nadie previó")

        with mock.patch.object(galeria, "_borrar_archivos", side_effect=inesperado):
            with self.assertLogs("django.db.backends.base", level="ERROR"):
                galeria.eliminar_imagen(self.producto, imagen.pk)  # no lanza

        self.assertEqual(galeria.listar(self.producto), [])
        self.assertEqual(len(self.archivos()), 3)  # se recogen al eliminar el producto
