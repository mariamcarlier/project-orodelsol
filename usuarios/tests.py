from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase


class ConsultarPerfilTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="cliente",
            password="ClaveSegura123!",
            first_name="María",
            last_name="Pérez",
            email="maria@example.com",
            rol="CLIENTE",
            tipo_documento="CC",
            documento="123456789",
            fecha_nacimiento=date(1995, 4, 12),
            telefono="3001234567",
        )
        self.otro_usuario = get_user_model().objects.create_user(
            username="otro",
            password="ClaveSegura123!",
            first_name="Otro",
            last_name="Usuario",
            email="otro@example.com",
            rol="MAYORISTA",
            tipo_documento="CE",
            documento="987654321",
            fecha_nacimiento=date(1988, 8, 20),
            telefono="3109876543",
        )

    def test_muestra_datos_del_usuario_autenticado(self):
        self.client.force_login(self.usuario)

        response = self.client.get("/usuario/perfil/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "María")
        self.assertContains(response, "Pérez")
        self.assertContains(response, "maria@example.com")
        self.assertContains(response, "123456789")
        self.assertContains(response, "12/04/1995")
        self.assertContains(response, "3001234567")
        self.assertContains(response, "Cliente")
        self.assertNotContains(response, self.otro_usuario.email)
        self.assertNotContains(response, self.otro_usuario.documento)
        self.assertNotContains(response, "<form", html=False)
        self.assertContains(response, 'href="/usuario/perfil/editar/"', html=False)

    def test_muestra_sin_resultados_para_campos_sin_dato(self):
        self.usuario.email = ""
        self.usuario.telefono = ""
        self.usuario.save(update_fields=["email", "telefono"])
        self.client.force_login(self.usuario)

        response = self.client.get("/usuario/perfil/")

        self.assertContains(response, "Sin resultados")

    def test_edicion_del_perfil_conserva_telefono_y_foto(self):
        self.client.force_login(self.usuario)

        response = self.client.get("/usuario/perfil/editar/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="telefono"', html=False)
        self.assertContains(response, 'name="foto"', html=False)
        self.assertContains(response, 'enctype="multipart/form-data"', html=False)

        response = self.client.post(
            "/usuario/perfil/editar/",
            {
                "first_name": "María",
                "last_name": "Pérez",
                "email": "maria@example.com",
                "tipo_documento": "CC",
                "documento": "123456789",
                "fecha_nacimiento": "1995-04-12",
                "telefono": "3005550101",
            },
        )

        self.assertRedirects(response, "/usuario/perfil/editar/")
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.telefono, "3005550101")

    def test_perfil_requiere_autenticacion(self):
        response = self.client.get("/usuario/perfil/")

        self.assertRedirects(
            response,
            "/admin/login/?next=/usuario/perfil/",
            fetch_redirect_response=False,
        )

# Create your tests here.
