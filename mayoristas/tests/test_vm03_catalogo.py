"""Pruebas de VM-03 (JODS-97): catálogo mayorista.

Lo que se comprueba, en el orden de los criterios de aceptación:

  1. Solo accede un mayorista aprobado (o administración).
  2. Solo aparecen productos con al menos una variante activa con stock.
  3. El precio «Desde» es el menor `precio_final` de esas variantes.
  4. Todo precio va con «Precio de referencia — sujeto a cotización».
  5. Sin tramos configurados se avisa y no se calcula nada.
  6. Nunca se dice «en fabricación».

Se construyen productos y variantes reales de `core`; no se simulan.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import (
    Coleccion,
    Material,
    Producto,
    Talla,
    VarianteProducto,
)
from mayoristas import selectors
from mayoristas.models import TramoPrecioReferencia

Usuario = get_user_model()

PREAVISO = "Precio de referencia — sujeto a cotización"


def crear_mayorista(nombre="mayo"):
    return Usuario.objects.create_user(
        username=nombre, email=f"{nombre}@ejemplo.com",
        password="Clave-segura-123", rol="MAYORISTA",
    )


class BaseCatalogoTests(TestCase):
    """Dos productos: uno disponible y otro agotado."""

    @classmethod
    def setUpTestData(cls):
        cls.coleccion = Coleccion.objects.create(nombre="Alma Dorada")
        cls.talla = Talla.objects.create(talla_us=Decimal("7.0"))
        cls.talla8 = Talla.objects.create(talla_us=Decimal("8.0"))
        cls.material = Material.objects.create(nombre="Oro 18K")

        cls.disponible = cls._producto(
            "AN-001", "Anillo Aurora", "Solitario", "100000"
        )
        cls._variante(cls.disponible, cls.talla, "AUR-7", 5, "20000")
        cls._variante(cls.disponible, cls.talla8, "AUR-8", 2, "45000")

        # Agotado: la única variante tiene stock 0.
        cls.agotado = cls._producto(
            "AN-002", "Anillo Eclipse", "Banda", "90000"
        )
        cls._variante(cls.agotado, cls.talla, "ECL-7", 0, "0")

        # Variante inactiva con stock: tampoco cuenta.
        cls.solo_inactiva = cls._producto(
            "AN-003", "Anillo Vela", "Sencillo", "80000"
        )
        cls._variante(cls.solo_inactiva, cls.talla, "VEL-7", 10, "0", activa=False)

    @classmethod
    def _producto(cls, codigo, nombre, detalle, precio):
        """Producto público mínimo con su talla y material habilitados.

        `Producto` exige las M2M `tallas` y `materiales`: sin ellas, la
        variante no pasaría `clean()`. Aquí se crean directamente con el ORM,
        que es lo que haría el panel de administración al guardar.
        """
        producto = Producto.objects.create(
            codigo=codigo, nombre=nombre, detalle=detalle,
            precio=Decimal(precio), coleccion=cls.coleccion,
        )
        producto.tallas.set([cls.talla, cls.talla8])
        producto.materiales.set([cls.material])
        return producto

    @classmethod
    def _variante(cls, producto, talla, sku, stock, adicional, activa=True):
        return VarianteProducto.objects.create(
            producto=producto, talla=talla, material=cls.material,
            sku=sku, stock=stock, precio_adicional=Decimal(adicional),
            activa=activa,
        )


# ─────────────────────────────────────────────────────────────────────
# 1. Acceso
# ─────────────────────────────────────────────────────────────────────

class AccesoCatalogoTests(BaseCatalogoTests):
    def test_anonimo_va_al_login(self):
        respuesta = self.client.get(reverse("mayoristas:catalogo"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login/", respuesta["Location"])

    def test_un_cliente_no_entra(self):
        cliente = Usuario.objects.create_user(
            username="cli", email="cli@ejemplo.com", password="Clave-segura-123",
        )
        self.client.force_login(cliente)
        respuesta = self.client.get(reverse("mayoristas:catalogo"))
        self.assertEqual(respuesta.status_code, 403)

    def test_un_mayorista_entra(self):
        self.client.force_login(crear_mayorista())
        respuesta = self.client.get(reverse("mayoristas:catalogo"))
        self.assertEqual(respuesta.status_code, 200)

    def test_un_administrador_entra(self):
        admin = Usuario.objects.create_user(
            username="adm", email="adm@ejemplo.com", password="Clave-segura-123",
            rol="ADMIN",
        )
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("mayoristas:catalogo")).status_code, 200)


# ─────────────────────────────────────────────────────────────────────
# 2. Disponibilidad (DEC-01)
# ─────────────────────────────────────────────────────────────────────

class DisponibilidadTests(BaseCatalogoTests):
    def test_solo_aparece_el_disponible(self):
        nombres = [p.nombre for p in selectors.catalogo_mayorista()]
        self.assertIn("Anillo Aurora", nombres)
        self.assertNotIn("Anillo Eclipse", nombres)
        self.assertNotIn("Anillo Vela", nombres)

    def test_una_variante_inactiva_no_hace_disponible_el_producto(self):
        producto = selectors.catalogo_mayorista().filter(pk=self.solo_inactiva.pk)
        self.assertFalse(producto.exists())

    def test_stock_positivo_con_variante_inactiva_tampoco(self):
        VarianteProducto.objects.filter(producto=self.solo_inactiva).update(
            activa=True, stock=0
        )
        self.assertFalse(
            selectors.catalogo_mayorista().filter(pk=self.solo_inactiva.pk).exists()
        )

    def test_cuenta_las_variantes_disponibles(self):
        producto = selectors.catalogo_mayorista().get(pk=self.disponible.pk)
        self.assertEqual(producto.variantes_disponibles, 2)

    def test_un_producto_borrador_no_aparece(self):
        self.disponible.es_borrador = True
        self.disponible.save(update_fields=["es_borrador"])
        self.assertFalse(
            selectors.catalogo_mayorista().filter(pk=self.disponible.pk).exists()
        )

    def test_una_coleccion_inactiva_oculta_sus_productos(self):
        self.coleccion.activa = False
        self.coleccion.save(update_fields=["activa"])
        self.assertEqual(selectors.catalogo_mayorista().count(), 0)


# ─────────────────────────────────────────────────────────────────────
# 3. Precio «Desde» (Q-01)
# ─────────────────────────────────────────────────────────────────────

class PrecioDesdeTests(BaseCatalogoTests):
    def test_precio_desde_es_el_menor_precio_final(self):
        """100 000 + 20 000 = 120 000, frente a 100 000 + 45 000 = 145 000."""
        producto = selectors.catalogo_mayorista().get(pk=self.disponible.pk)
        self.assertEqual(producto.precio_desde, Decimal("120000"))

    def test_el_precio_desde_ignora_variantes_sin_stock(self):
        VarianteProducto.objects.filter(sku="AUR-7").update(stock=0)
        producto = selectors.catalogo_mayorista().get(pk=self.disponible.pk)
        self.assertEqual(producto.precio_desde, Decimal("145000"))

    def test_el_precio_desde_ignora_variantes_inactivas(self):
        VarianteProducto.objects.filter(sku="AUR-7").update(activa=False)
        producto = selectors.catalogo_mayorista().get(pk=self.disponible.pk)
        self.assertEqual(producto.precio_desde, Decimal("145000"))

    def test_coincide_con_la_propiedad_precio_final(self):
        """La anotación SQL y la @property deben dar el mismo número."""
        producto = selectors.catalogo_mayorista().get(pk=self.disponible.pk)
        variantes = selectors.variantes_disponibles_de(self.disponible)
        menor = min(v.precio_final for v in variantes)
        self.assertEqual(producto.precio_desde, menor)

    def test_se_ordena_por_precio_ascendente(self):
        segundo = self._producto("AN-004", "Anillo Barato", "X", "50000")
        self._variante(segundo, self.talla, "BAR-7", 1, "0")
        precios = [p.precio_desde for p in selectors.catalogo_mayorista()]
        self.assertEqual(precios, sorted(precios))


# ─────────────────────────────────────────────────────────────────────
# 4 y 5. Pantalla: referencia obligatoria y tramos
# ─────────────────────────────────────────────────────────────────────

class PantallaCatalogoTests(BaseCatalogoTests):
    def setUp(self):
        self.client.force_login(crear_mayorista())

    def test_el_aviso_de_referencia_aparece(self):
        respuesta = self.client.get(reverse("mayoristas:catalogo"))
        self.assertContains(respuesta, PREAVISO)

    def test_cada_precio_es_de_referencia(self):
        """No hay ninguna cifra sin la aclaración al lado."""
        respuesta = self.client.get(reverse("mayoristas:catalogo"))
        self.assertContains(respuesta, "Desde")
        self.assertContains(respuesta, PREAVISO)

    def test_sin_tramos_avisa_de_configuracion_pendiente(self):
        respuesta = self.client.get(reverse("mayoristas:catalogo"))
        self.assertContains(respuesta, "Tramos pendientes de configuración")
        self.assertFalse(respuesta.context["hay_tramos"])

    def test_un_tramo_sin_porcentaje_no_cuenta_como_configurado(self):
        TramoPrecioReferencia.objects.create(
            nombre="Medio", cantidad_minima=10, cantidad_maxima=29
        )
        respuesta = self.client.get(reverse("mayoristas:catalogo"))
        self.assertFalse(respuesta.context["hay_tramos"])
        self.assertContains(respuesta, "Tramos pendientes de configuración")

    def test_con_tramos_configurados_se_listan(self):
        TramoPrecioReferencia.objects.create(
            nombre="Medio", cantidad_minima=10, cantidad_maxima=29,
            porcentaje=Decimal("5.00"),
        )
        respuesta = self.client.get(reverse("mayoristas:catalogo"))
        self.assertTrue(respuesta.context["hay_tramos"])
        self.assertContains(respuesta, "10 – 29")
        self.assertNotContains(respuesta, "Tramos pendientes de configuración")

    def test_no_dice_en_fabricacion(self):
        """DEC-01: no se promete lo que no está en stock."""
        respuesta = self.client.get(reverse("mayoristas:catalogo"))
        self.assertNotContains(respuesta, "en fabricación")
        self.assertNotContains(respuesta, "En fabricación")

    def test_el_producto_agotado_no_aparece_en_la_pantalla(self):
        respuesta = self.client.get(reverse("mayoristas:catalogo"))
        self.assertContains(respuesta, "Anillo Aurora")
        self.assertNotContains(respuesta, "Anillo Eclipse")

    def test_estado_vacio_honesto(self):
        Producto.objects.all().delete()
        respuesta = self.client.get(reverse("mayoristas:catalogo"))
        self.assertContains(respuesta, "No hay piezas para mostrar")
        self.assertNotContains(respuesta, "en fabricación")

    def test_busqueda_filtra(self):
        respuesta = self.client.get(
            reverse("mayoristas:catalogo"), {"q": "Aurora"}
        )
        self.assertEqual(respuesta.context["total"], 1)

    def test_busqueda_sin_resultados(self):
        respuesta = self.client.get(
            reverse("mayoristas:catalogo"), {"q": "no-existe"}
        )
        self.assertEqual(respuesta.context["total"], 0)
        self.assertContains(respuesta, "No hay piezas para mostrar")

    def test_variantes_disponibles_de_un_producto(self):
        variantes = selectors.variantes_disponibles_de(self.disponible)
        self.assertEqual([v.sku for v in variantes], ["AUR-7", "AUR-8"])

    def test_variantes_se_ordenan_por_precio_final(self):
        variantes = selectors.variantes_disponibles_de(self.disponible)
        precios = [v.precio_final for v in variantes]
        self.assertEqual(precios, sorted(precios))

    def test_producto_mayorista_devuelve_none_si_no_esta_disponible(self):
        self.assertIsNone(selectors.producto_mayorista(self.agotado.pk))
        self.assertIsNotNone(selectors.producto_mayorista(self.disponible.pk))