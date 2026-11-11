"""PROD-05 — Gestionar variantes del producto desde el panel (JODS-28).

Flujo simple: el administrador edita el producto en el panel y, en el mismo
formulario, agrega una variante (talla + material + SKU + stock). La variante
queda asociada al producto base; si la combinación ya existe, el sistema la
rechaza. Sin permiso `change_producto`, el panel deniega el acceso.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Coleccion, Material, Producto, Talla, VarianteProducto


class VariantePanelTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin-variantes",
            password="clave-de-prueba",
            first_name="Admin",
            last_name="Prueba",
            tipo_documento="CC",
            documento="123456792",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
        )
        self.client.force_login(self.admin)
        self.url = reverse("core:admin_section", kwargs={"seccion": "productos"})
        coleccion = Coleccion.objects.create(nombre="Panel")
        self.producto = Producto.objects.create(
            coleccion=coleccion,
            nombre="Anillo Panel",
            precio=Decimal("1500000.00"),
            imagen_url="https://example.com/panel.jpg",
        )
        self.talla = Talla.objects.create(talla_us=Decimal("7.0"))
        self.material = Material.objects.create(nombre="Oro amarillo 18K")
        self.producto.tallas.add(self.talla)
        self.producto.materiales.add(self.material)

    def datos_edicion_con_variante(self, sku="AN-0001-7-OA"):
        prefijo = f"productos-{self.producto.pk}"
        prefijo_var = f"variantes-{self.producto.pk}"
        return {
            "recurso": "productos",
            "accion": "edit",
            "registro": self.producto.pk,
            f"{prefijo}-codigo": self.producto.codigo,
            f"{prefijo}-nombre": "Anillo Panel",
            f"{prefijo}-coleccion": self.producto.coleccion_id,
            f"{prefijo}-detalle": "",
            f"{prefijo}-descripcion": "",
            f"{prefijo}-precio": "1500000",
            f"{prefijo}-imagen_url": "https://example.com/panel.jpg",
            f"{prefijo}-activo": "on",
            f"{prefijo}-tallas": [self.talla.pk],
            f"{prefijo}-materiales": [self.material.pk],
            f"{prefijo_var}-TOTAL_FORMS": "1",
            f"{prefijo_var}-INITIAL_FORMS": "0",
            f"{prefijo_var}-MIN_NUM_FORMS": "0",
            f"{prefijo_var}-MAX_NUM_FORMS": "1000",
            f"{prefijo_var}-0-id": "",
            f"{prefijo_var}-0-producto": self.producto.pk,
            f"{prefijo_var}-0-talla": self.talla.pk,
            f"{prefijo_var}-0-material": self.material.pk,
            f"{prefijo_var}-0-sku": sku,
            f"{prefijo_var}-0-peso_gramos": "3.50",
            f"{prefijo_var}-0-precio_adicional": "0",
            f"{prefijo_var}-0-stock": "5",
            f"{prefijo_var}-0-activa": "on",
        }

    def test_crear_variante_desde_el_panel(self):
        respuesta = self.client.post(self.url, self.datos_edicion_con_variante())

        self.assertEqual(respuesta.status_code, 302)
        variante = VarianteProducto.objects.get(sku="AN-0001-7-OA")
        self.assertEqual(variante.producto, self.producto)
        self.assertEqual(variante.talla, self.talla)
        self.assertEqual(variante.material, self.material)
        self.assertEqual(variante.stock, 5)
        self.assertTrue(variante.activa)

    def test_variante_duplicada_no_se_crea_dos_veces(self):
        self.client.post(self.url, self.datos_edicion_con_variante())
        self.assertEqual(VarianteProducto.objects.count(), 1)

        # Segunda edición con la misma combinación talla+material (otro SKU):
        # la restricción variante_unica debe rechazarla.
        respuesta = self.client.post(
            self.url, self.datos_edicion_con_variante(sku="OTRO-SKU")
        )

        self.assertEqual(respuesta.status_code, 200)  # formulario con error
        self.assertEqual(VarianteProducto.objects.count(), 1)

    def test_sin_permiso_no_se_puede_crear_variante(self):
        usuario = get_user_model().objects.create_user(
            username="staff-variantes",
            password="clave-de-prueba",
            tipo_documento="CC",
            documento="123456793",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
            is_staff=True,
        )
        self.client.force_login(usuario)

        respuesta = self.client.post(self.url, self.datos_edicion_con_variante())

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(VarianteProducto.objects.count(), 0)
