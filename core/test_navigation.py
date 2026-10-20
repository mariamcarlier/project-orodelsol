from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class NavigationAuthenticationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="nav-user",
            password="PruebaSegura123!",
            first_name="Juliana",
            last_name="Prueba",
            tipo_documento="CC",
            documento="874563210",
            fecha_nacimiento=date(1995, 5, 10),
            telefono="3007654321",
        )

    def test_navigation_shows_authenticated_user_and_post_logout(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("core:inicio"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hola, Juliana")
        self.assertContains(
            response,
            f'action="{reverse("core:cerrar_sesion")}"',
            html=False,
        )
        self.assertContains(response, 'name="csrfmiddlewaretoken"', html=False)

    def test_navigation_shows_login_for_anonymous_user(self):
        response = self.client.get(reverse("core:inicio"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("core:iniciar_sesion")}"',
            html=False,
        )
        self.assertNotContains(response, "Cerrar sesión")
