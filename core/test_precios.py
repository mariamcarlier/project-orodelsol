"""PROD-08 — Gestionar precios (JODS-31).

Decisión: sin historial de precios. Se valida el valor actual y que el cambio
se refleje de inmediato en la tienda y en el panel.

Criterios:
- Actualizar el precio de un producto.
- Validar que el precio sea numérico y positivo (sin letras ni negativos).
- El cambio se refleja inmediatamente.
- Sin autorización no se puede cambiar.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .dashboard import ProductoForm
from .models import Coleccion, Producto


class BasePreciosTests(TestCase):
    def setUp(self):
        self.coleccion = Coleccion.objects.create(nombre="Precios")
        self.producto = Producto.objects.create(
            coleccion=self.coleccion,
            nombre="Anillo Precio",
            precio=Decimal("1000000.00"),
            imagen_url="https://example.com/precio.jpg",
        )
        self.admin = get_user_model().objects.create_superuser(
            username="admin-precios",
            password="clave-de-prueba",
            first_name="Admin",
            last_name="Prueba",
            tipo_documento="CC",
            documento="123456798",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
        )
        self.url = reverse("core:admin_section", kwargs={"seccion": "productos"})

    def datos_edicion(self, precio):
        prefijo = f"productos-{self.producto.pk}"
        return {
            "recurso": "productos",
            "accion": "edit",
            "registro": self.producto.pk,
            f"{prefijo}-codigo": self.producto.codigo,
            f"{prefijo}-nombre": self.producto.nombre,
            f"{prefijo}-coleccion": self.coleccion.pk,
            f"{prefijo}-detalle": "",
            f"{prefijo}-descripcion": "",
            f"{prefijo}-precio": precio,
            f"{prefijo}-imagen_url": "https://example.com/precio.jpg",
            f"{prefijo}-activo": "on",
            f"variantes-{self.producto.pk}-TOTAL_FORMS": "0",
            f"variantes-{self.producto.pk}-INITIAL_FORMS": "0",
            f"variantes-{self.producto.pk}-MIN_NUM_FORMS": "0",
            f"variantes-{self.producto.pk}-MAX_NUM_FORMS": "1000",
        }


class ActualizarPrecioTests(BasePreciosTests):
    def test_actualizar_precio_desde_el_panel(self):
        self.client.force_login(self.admin)

        respuesta = self.client.post(self.url, self.datos_edicion("2350000.50"))

        self.assertEqual(respuesta.status_code, 302)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.precio, Decimal("2350000.50"))

    def test_el_cambio_se_refleja_de_inmediato_en_la_tienda(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, self.datos_edicion("2450000"))

        respuesta = self.client.get(reverse("core:inicio"))

        # La tarjeta pinta el precio con floatformat:0.
        self.assertContains(respuesta, "2450000")
        self.assertNotContains(respuesta, "1000000")

    def test_el_panel_muestra_el_precio_nuevo(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, self.datos_edicion("3100000"))

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, "3100000")

    def test_el_precio_final_de_la_variante_usa_el_precio_actualizado(self):
        from .models import Material, Talla, VarianteProducto

        talla = Talla.objects.create(talla_us=Decimal("7.0"))
        material = Material.objects.create(nombre="Oro amarillo 18K")
        self.producto.tallas.add(talla)
        self.producto.materiales.add(material)
        variante = VarianteProducto.objects.create(
            producto=self.producto,
            talla=talla,
            material=material,
            sku="AN-PRECIO-7",
            peso_gramos=Decimal("3.00"),
            precio_adicional=Decimal("50000"),
            stock=2,
        )
        self.client.force_login(self.admin)

        self.client.post(self.url, self.datos_edicion("2000000"))

        variante.refresh_from_db()
        self.assertEqual(variante.precio_final, Decimal("2050000.00"))


class ValidacionPrecioTests(BasePreciosTests):
    def test_precio_negativo_se_rechaza_en_el_modelo(self):
        self.producto.precio = Decimal("-1")

        with self.assertRaises(ValidationError) as contexto:
            self.producto.clean()

        self.assertIn("precio", contexto.exception.message_dict)

    def test_precio_negativo_se_rechaza_en_el_formulario(self):
        formulario = ProductoForm(
            data={
                "codigo": "",
                "nombre": "Anillo Negativo",
                "coleccion": self.coleccion.pk,
                "detalle": "",
                "descripcion": "",
                "precio": "-500000",
                "imagen_url": "https://example.com/negativo.jpg",
                "activo": "on",
            }
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn("precio", formulario.errors)

    def test_precio_no_numerico_se_rechaza(self):
        formulario = ProductoForm(
            data={
                "codigo": "",
                "nombre": "Anillo Texto",
                "coleccion": self.coleccion.pk,
                "detalle": "",
                "descripcion": "",
                "precio": "un millón",
                "imagen_url": "https://example.com/texto.jpg",
                "activo": "on",
            }
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn("precio", formulario.errors)

    def test_precio_cero_no_publica_el_producto(self):
        formulario = ProductoForm(
            data={
                "codigo": "",
                "nombre": "Anillo Gratis",
                "coleccion": self.coleccion.pk,
                "detalle": "",
                "descripcion": "",
                "precio": "0",
                "imagen_url": "https://example.com/gratis.jpg",
                "activo": "on",
            }
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn("mayor a cero", formulario.errors["precio"][0])

    def test_la_base_de_datos_rechaza_un_precio_negativo(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Producto.objects.create(
                    coleccion=self.coleccion,
                    nombre="Anillo BD",
                    precio=Decimal("-1"),
                )


class PrecioSinAutorizacionTests(BasePreciosTests):
    def test_sin_permiso_no_se_cambia_el_precio(self):
        usuario = get_user_model().objects.create_user(
            username="staff-precios",
            password="clave-de-prueba",
            tipo_documento="CC",
            documento="123456799",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
            is_staff=True,
        )
        self.client.force_login(usuario)

        respuesta = self.client.post(self.url, self.datos_edicion("999"))

        self.assertEqual(respuesta.status_code, 403)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.precio, Decimal("1000000.00"))
