from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .dashboard import RECURSOS
from .models import Coleccion, Producto


class InicioCatalogoTests(TestCase):
    def test_inicio_muestra_productos_desde_la_base_de_datos(self):
        coleccion = Coleccion.objects.create(
            nombre="Colección de prueba",
            temporada="2026",
        )
        Producto.objects.create(
            coleccion=coleccion,
            nombre="Anillo de prueba",
            precio="1250000.00",
            activo=True,
        )

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Anillo de prueba")
        self.assertContains(response, "Colección de prueba")


class PanelAdministracionTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_superuser(
            username="administrador",
            password="clave-de-prueba",
            first_name="Admin",
            last_name="Prueba",
            tipo_documento="CC",
            documento="123456789",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
        )
        self.client.force_login(usuario)

    def test_cada_recurso_tiene_pagina_y_plantilla_propia(self):
        for recurso in RECURSOS:
            with self.subTest(recurso=recurso["key"]):
                response = self.client.get(
                    reverse(
                        "core:admin_section",
                        kwargs={"seccion": recurso["key"]},
                    )
                )

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(
                    response,
                    f"admin_custom/sections/{recurso['key']}.html",
                )
                self.assertContains(response, recurso["title"])
                self.assertContains(response, "Ir a la tienda")

    def test_resumen_enlaza_a_las_paginas_de_recursos(self):
        response = self.client.get(reverse("core:admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        for recurso in RECURSOS:
            with self.subTest(recurso=recurso["key"]):
                self.assertContains(
                    response,
                    reverse(
                        "core:admin_section",
                        kwargs={"seccion": recurso["key"]},
                    ),
                )


class ColeccionCBVTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_user(
            username="crud",
            password="PruebaSegura123!",
            first_name="Usuario",
            last_name="Prueba",
            tipo_documento="CC",
            documento="987654321",
            fecha_nacimiento=date(1995, 5, 10),
            telefono="3007654321",
        )
        self.client.force_login(usuario)

    def test_listado_muestra_titulo_y_colecciones(self):
        Coleccion.objects.create(nombre="Luz Dorada", temporada="Clásica")

        response = self.client.get(reverse("core:coleccion_listar"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Colecciones")
        self.assertContains(response, "Luz Dorada")

    def test_crear_y_actualizar_coleccion(self):
        create_response = self.client.post(
            reverse("core:coleccion_crear"),
            {
                "nombre": "Luz Dorada",
                "descripcion": "Diseños clásicos",
                "temporada": "Clásica",
                "imagen_url": "",
                "activa": "on",
            },
        )
        coleccion = Coleccion.objects.get(nombre="Luz Dorada")

        self.assertRedirects(create_response, reverse("core:coleccion_listar"))

        update_response = self.client.post(
            reverse("core:coleccion_editar", kwargs={"pk": coleccion.pk}),
            {
                "nombre": "Luz Dorada 2026",
                "descripcion": "Diseños clásicos actualizados",
                "temporada": "2026",
                "imagen_url": "",
                "activa": "on",
            },
        )
        coleccion.refresh_from_db()

        self.assertRedirects(update_response, reverse("core:coleccion_listar"))
        self.assertEqual(coleccion.nombre, "Luz Dorada 2026")

    def test_eliminar_coleccion_por_post(self):
        coleccion = Coleccion.objects.create(nombre="Temporal")

        response = self.client.post(
            reverse("core:coleccion_eliminar", kwargs={"pk": coleccion.pk})
        )

        self.assertRedirects(response, reverse("core:coleccion_listar"))
        self.assertFalse(Coleccion.objects.filter(pk=coleccion.pk).exists())

    def test_eliminar_coleccion_con_productos_muestra_error(self):
        coleccion = Coleccion.objects.create(nombre="Con productos")
        Producto.objects.create(
            coleccion=coleccion,
            nombre="Anillo de prueba",
            precio="100000.00",
        )

        response = self.client.post(
            reverse("core:coleccion_eliminar", kwargs={"pk": coleccion.pk}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tiene productos asociados")
        self.assertTrue(Coleccion.objects.filter(pk=coleccion.pk).exists())


class AuthenticationViewTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="acceso",
            password="PruebaSegura123!",
            first_name="Usuario",
            last_name="Autenticado",
            tipo_documento="CC",
            documento="123450987",
            fecha_nacimiento=date(1992, 3, 14),
            telefono="3001230098",
        )

    def test_login_view_muestra_formulario_y_conserva_next(self):
        response = self.client.get(
            reverse("core:iniciar_sesion"),
            {"next": reverse("core:producto_listar")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")
        self.assertContains(response, 'name="csrfmiddlewaretoken"', html=False)
        self.assertContains(response, 'name="next"', html=False)

    def test_login_y_logout(self):
        login_response = self.client.post(
            reverse("core:iniciar_sesion"),
            {"username": self.usuario.username, "password": "PruebaSegura123!"},
        )
        self.assertRedirects(login_response, reverse("usuarios:perfil"))

        logout_response = self.client.post(reverse("core:cerrar_sesion"))
        self.assertRedirects(logout_response, reverse("core:iniciar_sesion"))

    def test_logout_rechaza_get(self):
        response = self.client.get(reverse("core:cerrar_sesion"))

        self.assertEqual(response.status_code, 405)
