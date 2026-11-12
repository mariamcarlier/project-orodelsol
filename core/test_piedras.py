"""PROD-11 — Gestionar tallas, materiales y piedras (JODS-34).

Decisiones del equipo:
- Catálogo maestro de 9 piedras (A–I) con imagen, cargado por el seed.
- Activar/desactivar por producto = asignar o no la piedra (M2M).
- Bandera `personalizable`: si está activa exige al menos una piedra.
- El cliente elige la piedra en la tarjeta; solo ve las asignadas, y el
  servidor confirma la disponibilidad antes de agregarla al carrito.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .dashboard import ProductoForm
from .models import Coleccion, Material, Piedra, Producto, Talla


def crear_admin(usuario="admin-piedras", documento="123456796"):
    return get_user_model().objects.create_superuser(
        username=usuario,
        password="clave-de-prueba",
        first_name="Admin",
        last_name="Prueba",
        tipo_documento="CC",
        documento=documento,
        fecha_nacimiento=date(1990, 1, 1),
        telefono="3001234567",
    )


class CatalogoPiedrasTests(TestCase):
    def test_el_seed_carga_las_nueve_referencias(self):
        call_command("seed_tallas_materiales", verbosity=0)

        self.assertEqual(Piedra.objects.count(), 9)
        cristal = Piedra.objects.get(ref="A")
        self.assertEqual(cristal.nombre, "Cristal")
        self.assertEqual(cristal.imagen, "img/piedras/A-Cristal.webp")
        self.assertEqual(
            list(Piedra.objects.values_list("ref", flat=True)),
            list("ABCDEFGHI"),
        )

    def test_el_seed_es_idempotente(self):
        call_command("seed_tallas_materiales", verbosity=0)
        call_command("seed_tallas_materiales", verbosity=0)

        self.assertEqual(Piedra.objects.count(), 9)
        self.assertEqual(Talla.objects.count(), 19)
        self.assertEqual(Material.objects.count(), 1)

    def test_la_referencia_de_piedra_es_unica(self):
        from django.db import IntegrityError

        Piedra.objects.create(ref="A", nombre="Cristal", imagen="img/piedras/A-Cristal.webp")

        with self.assertRaises(IntegrityError):
            Piedra.objects.create(ref="A", nombre="Otro cristal")


class PiedrasDelProductoTests(TestCase):
    def setUp(self):
        self.coleccion = Coleccion.objects.create(nombre="Piedras")
        self.producto = Producto.objects.create(
            coleccion=self.coleccion,
            nombre="Anillo con piedra",
            precio=Decimal("2000000"),
            imagen_url="https://example.com/piedra.jpg",
            personalizable=True,
        )
        self.cristal, _ = Piedra.objects.get_or_create(
            ref="A", defaults={"nombre": "Cristal", "imagen": "img/piedras/A-Cristal.webp"}
        )
        self.fucsia, _ = Piedra.objects.get_or_create(
            ref="H", defaults={"nombre": "Fucsia", "imagen": "img/piedras/H-Fucsia.webp"}
        )

    def test_asignar_y_desactivar_piedras_por_producto(self):
        self.producto.piedras.add(self.cristal, self.fucsia)
        self.assertEqual(self.producto.piedras.count(), 2)

        # Desactivar = quitar la relación del producto.
        self.producto.piedras.remove(self.fucsia)

        self.assertEqual(list(self.producto.piedras_disponibles()), [self.cristal])

    def test_el_modelo_exige_piedra_al_publicar_un_personalizable(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError) as contexto:
            self.producto.clean()

        self.assertIn("personalizable", contexto.exception.message_dict)

    def test_formulario_exige_piedra_al_publicar_un_personalizable(self):
        formulario = ProductoForm(
            data={
                "codigo": self.producto.codigo,
                "nombre": self.producto.nombre,
                "coleccion": self.coleccion.pk,
                "detalle": "",
                "descripcion": "",
                "precio": "2000000",
                "imagen_url": "https://example.com/piedra.jpg",
                "activo": "on",
                "personalizable": "on",
                # sin piedras
            }
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn("piedras", formulario.errors)
        self.assertIn("al menos una piedra", formulario.errors["piedras"][0])

    def test_borrador_personalizable_sin_piedra_se_puede_guardar(self):
        formulario = ProductoForm(
            data={
                "codigo": "",
                "nombre": self.producto.nombre,
                "coleccion": self.coleccion.pk,
                "detalle": "",
                "descripcion": "",
                "precio": "2000000",
                "imagen_url": "",
                "activo": "on",
                "es_borrador": "on",
                "personalizable": "on",
            }
        )

        self.assertTrue(formulario.is_valid(), formulario.errors)

    def test_formulario_acepta_personalizable_con_piedra(self):
        formulario = ProductoForm(
            data={
                "codigo": "",
                "nombre": self.producto.nombre,
                "coleccion": self.coleccion.pk,
                "detalle": "",
                "descripcion": "",
                "precio": "2000000",
                "imagen_url": "https://example.com/piedra.jpg",
                "activo": "on",
                "personalizable": "on",
                "piedras": [self.cristal.pk],
            }
        )

        self.assertTrue(formulario.is_valid(), formulario.errors)


class PiedrasEnLaTiendaTests(TestCase):
    def setUp(self):
        self.coleccion = Coleccion.objects.create(nombre="Vitrina")
        self.producto = Producto.objects.create(
            coleccion=self.coleccion,
            nombre="Anillo Vitrina",
            precio=Decimal("1800000"),
            imagen_url="https://example.com/vitrina.jpg",
            personalizable=True,
        )
        self.activa = Piedra.objects.create(
            ref="A", nombre="Cristal", imagen="img/piedras/A-Cristal.webp"
        )
        self.desactivada = Piedra.objects.create(
            ref="H", nombre="Fucsia", imagen="img/piedras/H-Fucsia.webp"
        )
        self.producto.piedras.add(self.activa)

    def test_el_cliente_solo_ve_las_piedras_asignadas(self):
        respuesta = self.client.get(reverse("core:inicio"))

        self.assertContains(respuesta, 'data-stone-ref="A"')
        self.assertContains(respuesta, "Cristal")
        self.assertNotContains(respuesta, 'data-stone-ref="H"')
        self.assertNotContains(respuesta, "Fucsia")

    def test_la_imagen_de_la_piedra_se_pinta_desde_static(self):
        respuesta = self.client.get(reverse("core:inicio"))

        self.assertContains(respuesta, "img/piedras/A-Cristal.webp")

    def test_la_guarda_permite_la_piedra_asignada(self):
        url = reverse(
            "core:producto_piedra_disponible",
            args=[self.producto.pk, self.activa.ref],
        )

        respuesta = self.client.get(url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["disponible"])

    def test_la_guarda_rechaza_una_piedra_desactivada(self):
        url = reverse(
            "core:producto_piedra_disponible",
            args=[self.producto.pk, self.desactivada.ref],
        )

        respuesta = self.client.get(url)

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(respuesta.json()["disponible"])

    def test_la_guarda_acepta_la_referencia_en_minusculas(self):
        url = reverse(
            "core:producto_piedra_disponible",
            args=[self.producto.pk, "a"],
        )

        self.assertEqual(self.client.get(url).status_code, 200)

    def test_la_guarda_rechaza_productos_no_publicos(self):
        self.producto.es_borrador = True
        self.producto.save(update_fields=["es_borrador"])
        url = reverse(
            "core:producto_piedra_disponible",
            args=[self.producto.pk, self.activa.ref],
        )

        self.assertEqual(self.client.get(url).status_code, 400)

    def test_un_producto_no_personalizable_no_muestra_piedras(self):
        self.producto.personalizable = False
        self.producto.save(update_fields=["personalizable"])

        respuesta = self.client.get(reverse("core:inicio"))

        self.assertNotContains(respuesta, 'data-stone-ref="A"')


class PiedrasSinAutorizacionTests(TestCase):
    def test_sin_permiso_no_se_puede_editar_piedras_del_producto(self):
        coleccion = Coleccion.objects.create(nombre="Seguridad")
        producto = Producto.objects.create(
            coleccion=coleccion,
            nombre="Anillo Seguro",
            precio=Decimal("900000"),
            imagen_url="https://example.com/seguro.jpg",
        )
        piedra = Piedra.objects.create(ref="A", nombre="Cristal")
        usuario = get_user_model().objects.create_user(
            username="staff-piedras",
            password="clave-de-prueba",
            tipo_documento="CC",
            documento="123456797",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
            is_staff=True,
        )
        self.client.force_login(usuario)

        respuesta = self.client.post(
            reverse("core:admin_section", kwargs={"seccion": "productos"}),
            {
                "recurso": "productos",
                "accion": "edit",
                "registro": producto.pk,
                f"productos-{producto.pk}-piedras": [piedra.pk],
            },
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(producto.piedras.exists())
