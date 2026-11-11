"""Al eliminar un producto se limpian sus archivos (carpeta `productos/<id>/`).

Django borra las filas de `ProductoImagen` en cascada, pero no los archivos.
La limpieza la dispara `core/signals.py` y la ejecuta
`servicio_galeria.borrar_carpeta_de_producto`, siempre después de confirmar la
transacción. Cada prueba usa un `MEDIA_ROOT` temporal (ver `_Base`).
"""

from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
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
