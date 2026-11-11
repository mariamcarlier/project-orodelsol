"""El esquema de galería no debe abrir subidas de archivos sin validar.

`Coleccion.imagen` existe desde la migración 0007. Desde el Paso 04 la portada
se sube, ya validada, desde el panel y el formulario de colecciones
(`ColeccionForm`). El admin de Django genera su propio formulario, sin esa
validación, así que NO debe ofrecerla (un `ModelAdmin` sin `fields` muestra
todos los campos editables, incluido este).
"""

import shutil
import tempfile
from datetime import date
from io import BytesIO

from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Coleccion, Producto, ProductoImagen


def gif_real():
    buffer = BytesIO()
    Image.new("RGB", (4, 4)).save(buffer, "GIF")
    return buffer.getvalue()


class AdminColeccionSinSubidaTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="oro-del-sol-admin-")
        self.addCleanup(shutil.rmtree, self.media, True)
        contexto = override_settings(MEDIA_ROOT=self.media)
        contexto.enable()
        self.addCleanup(contexto.disable)
        administrador = get_user_model().objects.create_superuser(
            username="administrador",
            password="clave-de-prueba",
            first_name="Admin",
            last_name="Prueba",
            tipo_documento="CC",
            documento="123456789",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
        )
        self.client.force_login(administrador)

    def archivos_en_media(self):
        import os

        return [f for _, _, nombres in os.walk(self.media) for f in nombres]

    def test_el_formulario_de_alta_no_ofrece_subir_archivo(self):
        respuesta = self.client.get(reverse("admin:core_coleccion_add"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'name="imagen"')
        self.assertNotContains(respuesta, 'type="file"')

    def test_el_formulario_de_edicion_no_ofrece_subir_archivo(self):
        coleccion = Coleccion.objects.create(nombre="Luna")

        respuesta = self.client.get(
            reverse("admin:core_coleccion_change", args=[coleccion.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'name="imagen"')

    def test_un_archivo_enviado_a_mano_se_ignora(self):
        self.client.post(
            reverse("admin:core_coleccion_add"),
            {
                "nombre": "Con intento de subida",
                "descripcion": "",
                "temporada": "",
                "imagen_url": "",
                "activa": "on",
                "imagen": SimpleUploadedFile("x.gif", gif_real()),
            },
        )

        coleccion = Coleccion.objects.get(nombre="Con intento de subida")
        self.assertFalse(coleccion.imagen)
        self.assertEqual(self.archivos_en_media(), [])

    def test_la_portada_por_url_sigue_editable_en_el_admin(self):
        respuesta = self.client.get(reverse("admin:core_coleccion_add"))

        self.assertContains(respuesta, 'name="imagen_url"')

    def test_la_galeria_y_el_marcador_no_se_exponen_en_el_admin_de_producto(self):
        respuesta = self.client.get(reverse("admin:core_producto_add"))

        self.assertNotContains(respuesta, "galeria_gestionada")
        self.assertFalse(django_admin.site.is_registered(ProductoImagen))
        self.assertEqual(Producto.objects.count(), 0)
