"""PROD-04 — Gestionar código y referencia del producto (JODS-27).

Criterios cubiertos aquí (el resto ya está en test_variantes.py):
- El código se muestra en la información administrativa (listado clásico).
- El código se muestra en el panel (dashboard) y se puede buscar por él.
- El formulario rechaza un código duplicado con error legible (no 500),
  incluso si se escribe en minúsculas.
- Sin el permiso requerido, el panel deniega el acceso (403).
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .dashboard import ProductoForm
from .models import Coleccion, Producto


def crear_producto(**extra):
    coleccion, _ = Coleccion.objects.get_or_create(nombre="Alma Dorada")
    datos = {
        "coleccion": coleccion,
        "nombre": "Anillo Aurora",
        "precio": "1000000.00",
        "imagen_url": "https://example.com/aurora.jpg",
    }
    datos.update(extra)
    return Producto.objects.create(**datos)


class CodigoVisibleAdminTests(TestCase):
    def test_codigo_se_muestra_en_el_listado_clasico(self):
        producto = crear_producto(codigo="AN-0042")
        usuario = get_user_model().objects.create_superuser(
            username="admin-codigo",
            password="clave-de-prueba",
            first_name="Admin",
            last_name="Prueba",
            tipo_documento="CC",
            documento="123456789",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
        )
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse("core:producto_listar"))

        self.assertContains(respuesta, producto.codigo)
        self.assertContains(respuesta, producto.nombre)

    def test_codigo_se_muestra_en_el_panel_y_se_busca_por_codigo(self):
        crear_producto(codigo="AN-0042", nombre="Anillo Aurora")
        crear_producto(codigo="AN-0099", nombre="Anillo Luna")
        usuario = get_user_model().objects.create_superuser(
            username="admin-panel",
            password="clave-de-prueba",
            first_name="Admin",
            last_name="Prueba",
            tipo_documento="CC",
            documento="123456790",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
        )
        self.client.force_login(usuario)
        url = reverse("core:admin_section", kwargs={"seccion": "productos"})

        respuesta = self.client.get(url)
        self.assertContains(respuesta, "AN-0042")

        respuesta = self.client.get(url, {"q": "AN-0042"})
        self.assertContains(respuesta, "Anillo Aurora")
        self.assertNotContains(respuesta, "Anillo Luna")

    def test_str_incluye_codigo_para_identificar_el_producto(self):
        producto = crear_producto(codigo="AN-0001", nombre="Anillo Aurora")

        self.assertEqual(str(producto), "AN-0001 - Anillo Aurora")


class CodigoDuplicadoFormularioTests(TestCase):
    def test_formulario_rechaza_codigo_duplicado_en_minusculas(self):
        crear_producto(codigo="AN-0001")
        coleccion = Coleccion.objects.get(nombre="Alma Dorada")
        formulario = ProductoForm(
            data={
                "codigo": "an-0001",
                "nombre": "Otro anillo",
                "coleccion": coleccion.pk,
                "detalle": "",
                "descripcion": "",
                "precio": "500000",
                "imagen_url": "https://example.com/otro.jpg",
            }
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn("codigo", formulario.errors)

    def test_formulario_acepta_codigo_nuevo_y_vacio_autogenera(self):
        coleccion = Coleccion.objects.get_or_create(nombre="Alma Dorada")[0]
        base = {
            "nombre": "Anillo Nuevo",
            "coleccion": coleccion.pk,
            "detalle": "",
            "descripcion": "",
            "precio": "500000",
            "imagen_url": "https://example.com/nuevo.jpg",
        }

        con_codigo = ProductoForm(data={**base, "codigo": "REF-100"})
        self.assertTrue(con_codigo.is_valid(), con_codigo.errors)
        self.assertEqual(con_codigo.save().codigo, "REF-100")

        sin_codigo = ProductoForm(data={**base, "codigo": ""})
        self.assertTrue(sin_codigo.is_valid(), sin_codigo.errors)
        self.assertEqual(sin_codigo.save().codigo, "AN-0001")


class CodigoPublicoTests(TestCase):
    """Decisión: el código también se muestra en la tienda (Ref.)."""

    def test_codigo_se_muestra_en_la_tienda_solo_para_publicos(self):
        crear_producto(codigo="AN-0042", nombre="Anillo Visible")
        crear_producto(codigo="AN-0099", nombre="Anillo Borrador", es_borrador=True)

        respuesta = self.client.get(reverse("core:inicio"))

        self.assertContains(respuesta, "Ref. AN-0042")
        self.assertNotContains(respuesta, "AN-0099")


class CodigoSinAutorizacionTests(TestCase):
    def test_panel_deniega_acceso_sin_permiso_de_producto(self):
        usuario = get_user_model().objects.create_user(
            username="staff-sin-permiso",
            password="clave-de-prueba",
            tipo_documento="CC",
            documento="123456791",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
            is_staff=True,
        )
        self.client.force_login(usuario)

        respuesta = self.client.get(
            reverse("core:admin_section", kwargs={"seccion": "productos"})
        )

        self.assertEqual(respuesta.status_code, 403)
