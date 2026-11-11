"""PROD-12 — Guardar producto como borrador (JODS-35).

Reglas (simples):
- Un borrador se guarda aunque esté incompleto (sin nombre, sin precio,
  sin imagen). No aparece en la tienda.
- Se puede editar y completar después; los datos se conservan.
- Al publicar (activo y no borrador) se exigen nombre y precio > 0, con un
  error específico por campo, no un mensaje genérico.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .dashboard import ProductoForm
from .models import Coleccion, Producto


class BaseBorradorTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin-borrador",
            password="clave-de-prueba",
            first_name="Admin",
            last_name="Prueba",
            tipo_documento="CC",
            documento="123456794",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
        )
        self.client.force_login(self.admin)
        self.coleccion = Coleccion.objects.create(nombre="Borradores")

    def datos_formulario(self, **extra):
        datos = {
            "codigo": "",
            "nombre": "",
            "coleccion": self.coleccion.pk,
            "detalle": "",
            "descripcion": "",
            "precio": "",
            "imagen_url": "",
            "activo": "on",
            "es_borrador": "on",
        }
        datos.update(extra)
        return datos


class GuardarBorradorTests(BaseBorradorTests):
    def test_borrador_incompleto_se_puede_guardar(self):
        formulario = ProductoForm(data=self.datos_formulario())

        self.assertTrue(formulario.is_valid(), formulario.errors)
        producto = formulario.save()

        self.assertTrue(producto.es_borrador)
        self.assertEqual(producto.nombre, "")
        self.assertEqual(producto.precio, Decimal("0"))
        self.assertTrue(producto.codigo)  # código autogenerado
        self.assertFalse(producto.es_publico)

    def test_borrador_no_aparece_en_la_tienda(self):
        Producto.objects.create(
            coleccion=self.coleccion,
            nombre="Anillo Oculto",
            precio=Decimal("900000"),
            es_borrador=True,
        )

        respuesta = self.client.get(reverse("core:inicio"))

        self.assertNotContains(respuesta, "Anillo Oculto")

    def test_borrador_se_puede_editar_despues_y_conserva_datos(self):
        producto = ProductoForm(data=self.datos_formulario()).save()
        producto.refresh_from_db()
        url = reverse("core:admin_section", kwargs={"seccion": "productos"})
        prefijo = f"productos-{producto.pk}"

        respuesta = self.client.post(
            url,
            {
                "recurso": "productos",
                "accion": "edit",
                "registro": producto.pk,
                f"{prefijo}-codigo": producto.codigo,
                f"{prefijo}-nombre": "Anillo Terminado",
                f"{prefijo}-coleccion": self.coleccion.pk,
                f"{prefijo}-detalle": "Detalle guardado",
                f"{prefijo}-descripcion": "Descripción guardada",
                f"{prefijo}-precio": "1250000",
                f"{prefijo}-imagen_url": "https://example.com/terminado.jpg",
                f"{prefijo}-activo": "on",
                # sin es_borrador => deja de ser borrador
                f"variantes-{producto.pk}-TOTAL_FORMS": "0",
                f"variantes-{producto.pk}-INITIAL_FORMS": "0",
                f"variantes-{producto.pk}-MIN_NUM_FORMS": "0",
                f"variantes-{producto.pk}-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        producto.refresh_from_db()
        self.assertEqual(producto.nombre, "Anillo Terminado")
        self.assertEqual(producto.detalle, "Detalle guardado")
        self.assertEqual(producto.precio, Decimal("1250000.00"))
        self.assertFalse(producto.es_borrador)
        self.assertTrue(producto.es_publico)


class PublicarProductoTests(BaseBorradorTests):
    def test_publicar_incompleto_da_error_especifico_por_campo(self):
        formulario = ProductoForm(
            data=self.datos_formulario(es_borrador="", precio="0")
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn("nombre", formulario.errors)
        self.assertIn("precio", formulario.errors)
        self.assertIn("obligatorio", formulario.errors["nombre"][0])
        self.assertIn("mayor a cero", formulario.errors["precio"][0])

    def test_el_panel_muestra_el_error_sin_crear_el_producto(self):
        url = reverse("core:admin_section", kwargs={"seccion": "productos"})
        datos = {"recurso": "productos", "accion": "create"}
        for campo, valor in self.datos_formulario(es_borrador="", precio="0").items():
            datos[f"productos-nuevo-{campo}"] = valor

        respuesta = self.client.post(url, datos)

        self.assertEqual(respuesta.status_code, 200)  # se queda en el formulario
        self.assertContains(respuesta, "obligatorio para publicar")
        self.assertFalse(Producto.objects.exists())

    def test_publicar_completo_funciona(self):
        formulario = ProductoForm(
            data=self.datos_formulario(
                es_borrador="",
                nombre="Anillo Publicado",
                precio="1500000",
                imagen_url="https://example.com/publicado.jpg",
            )
        )

        self.assertTrue(formulario.is_valid(), formulario.errors)
        producto = formulario.save()

        self.assertTrue(producto.es_publico)


class PublicarBorradorMasivoTests(BaseBorradorTests):
    def test_activar_masivamente_publica_el_borrador_completo(self):
        completo = Producto.objects.create(
            coleccion=self.coleccion,
            nombre="Borrador Completo",
            precio=Decimal("1000000"),
            imagen_url="https://example.com/completo.jpg",
            es_borrador=True,
            activo=False,
        )
        incompleto = Producto.objects.create(
            coleccion=self.coleccion,
            nombre="",
            precio=Decimal("0"),
            es_borrador=True,
            activo=False,
        )
        url = reverse("core:admin_section", kwargs={"seccion": "productos"})

        respuesta = self.client.post(
            url,
            {
                "recurso": "productos",
                "accion": "bulk",
                "estado": "1",
                "registros": [completo.pk, incompleto.pk],
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        completo.refresh_from_db()
        incompleto.refresh_from_db()
        self.assertTrue(completo.es_publico)
        self.assertTrue(incompleto.es_borrador)
        self.assertFalse(incompleto.activo)


class BorradorSinAutorizacionTests(BaseBorradorTests):
    def test_sin_permiso_no_se_crea_borrador(self):
        usuario = get_user_model().objects.create_user(
            username="staff-borrador",
            password="clave-de-prueba",
            tipo_documento="CC",
            documento="123456795",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
            is_staff=True,
        )
        self.client.force_login(usuario)
        url = reverse("core:admin_section", kwargs={"seccion": "productos"})
        datos = {"recurso": "productos", "accion": "create"}
        for campo, valor in self.datos_formulario().items():
            datos[f"productos-nuevo-{campo}"] = valor

        respuesta = self.client.post(url, datos)

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Producto.objects.exists())
