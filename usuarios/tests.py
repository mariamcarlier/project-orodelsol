from datetime import date
import re

from django.contrib.auth import get_user_model
from django.core import mail
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
            "/accounts/login/?next=/usuario/perfil/",
            fetch_redirect_response=False,
        )

    def test_login_y_recuperacion_de_contrasena_estan_disponibles(self):
        for url in ("/accounts/login/", "/accounts/password_reset/"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "Registra un usuario")
                self.assertNotContains(response, 'href="/register/"', html=False)

    def test_login_muestra_control_accesible_para_ver_contrasena(self):
        response = self.client.get("/accounts/login/")

        self.assertContains(response, 'type="password"', html=False)
        self.assertContains(response, "data-password-toggle", html=False)
        self.assertContains(response, 'aria-label="Mostrar contraseña"', html=False)
        self.assertContains(response, 'aria-controls="id_password"', html=False)

    def test_registro_requiere_autenticacion(self):
        response = self.client.get("/register/")

        self.assertRedirects(
            response,
            "/accounts/login/?next=/register/",
            fetch_redirect_response=False,
        )

    def test_administrador_puede_registrar_usuario(self):
        administrador = get_user_model().objects.create_user(
            username="administrador",
            password="AdminPass123!",
            rol="ADMIN",
            tipo_documento="CC",
            documento="1122334455",
            fecha_nacimiento=date(1980, 1, 1),
            telefono="3001112233",
        )
        self.client.force_login(administrador)

        response = self.client.post(
            "/register/",
            {
                "username": "nuevo",
                "email": "nuevo@example.com",
                "first_name": "Nuevo",
                "last_name": "Usuario",
                "tipo_documento": "CC",
                "documento": "5566778899",
                "fecha_nacimiento": "2000-05-20",
                "telefono": "3005556677",
                "rol": "CLIENTE",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, "/usuario/registrar/")
        nuevo_usuario = get_user_model().objects.get(username="nuevo")
        self.assertEqual(nuevo_usuario.telefono, "3005556677")
        self.assertTrue(nuevo_usuario.check_password("StrongPass123!"))

    def test_recuperacion_envia_enlace_funcional(self):
        response = self.client.post(
            "/accounts/password_reset/",
            {"email": self.usuario.email},
        )

        self.assertRedirects(response, "/accounts/password_reset/done/")
        self.assertEqual(len(mail.outbox), 1)
        reset_url = re.search(r"http://testserver(\S+)", mail.outbox[0].body)
        self.assertIsNotNone(reset_url)

        response = self.client.get(reset_url.group(1))
        self.assertEqual(response.status_code, 302)
        set_password_url = response["Location"]
        response = self.client.post(
            set_password_url,
            {
                "new_password1": "NewStrongPass123!",
                "new_password2": "NewStrongPass123!",
            },
        )

        self.assertRedirects(response, "/accounts/reset/done/")
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("NewStrongPass123!"))

# Create your tests here.
