import re
from datetime import date

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase


class ConsultarPerfilTests(TestCase):
    def setUp(self):
        cache.clear()
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
        self.assertNotContains(response, 'name="first_name"', html=False)
        self.assertContains(response, 'action="/accounts/logout/"', html=False)
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

    def test_login_enlaza_al_registro_publico(self):
        response = self.client.get("/accounts/login/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/register/"', html=False)

    def test_registro_publico_crea_cliente_sin_permisos_admin(self):
        response = self.client.post(
            "/register/",
            {
                "username": "nuevo_cliente",
                "email": "cliente.nuevo@example.com",
                "first_name": "Nuevo",
                "last_name": "Cliente",
                "tipo_documento": "CC",
                "documento": "5566778899",
                "fecha_nacimiento": "2000-05-20",
                "telefono": "3005556677",
                "rol": "ADMIN",
                "is_staff": "on",
                "is_superuser": "on",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
            follow=True,
        )

        self.assertEqual(response.redirect_chain, [("/accounts/login/", 302)])
        self.assertContains(response, "Tu cuenta se creó correctamente")
        nuevo_usuario = get_user_model().objects.get(username="nuevo_cliente")
        self.assertEqual(nuevo_usuario.rol, "CLIENTE")
        self.assertFalse(nuevo_usuario.is_staff)
        self.assertFalse(nuevo_usuario.is_superuser)
        self.assertTrue(nuevo_usuario.check_password("StrongPass123!"))
        self.assertEqual(len(mail.outbox), 0)

    def test_registro_publico_muestra_formulario_sin_selector_de_rol(self):
        response = self.client.get("/register/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Crear cuenta")
        self.assertNotContains(response, 'name="rol"', html=False)

    def test_login_renderiza_cada_campo_una_vez_y_conserva_el_destino(self):
        response = self.client.get(
            "/accounts/login/",
            {"next": "/usuario/perfil/"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<input type="hidden" name="next" value="/usuario/perfil/">',
            html=False,
        )
        self.assertEqual(response.content.count(b'name="username"'), 1)
        self.assertEqual(response.content.count(b'name="password"'), 1)

    def test_login_exitoso_redirige_al_destino_solicitado(self):
        self.usuario.set_password("SecureTestPassword123!")
        self.usuario.save(update_fields=["password"])

        response = self.client.post(
            "/accounts/login/",
            {
                "username": self.usuario.username,
                "password": "SecureTestPassword123!",
                "next": "/usuario/perfil/",
            },
        )

        self.assertRedirects(
            response,
            "/usuario/perfil/",
            fetch_redirect_response=False,
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_rechaza_destino_externo(self):
        self.usuario.set_password("SecureTestPassword123!")
        self.usuario.save(update_fields=["password"])

        response = self.client.post(
            "/accounts/login/",
            {
                "username": self.usuario.username,
                "password": "SecureTestPassword123!",
                "next": "https://atacante.example/",
            },
        )

        self.assertRedirects(
            response,
            "/profile/",
            fetch_redirect_response=False,
        )

    def test_login_fallido_muestra_error_generico(self):
        response = self.client.post(
            "/accounts/login/",
            {"username": self.usuario.username, "password": "incorrecta"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Por favor, introduzca un nombre de usuario")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_bloquea_el_sexto_intento_fallido_por_usuario_e_ip(self):
        self.usuario.set_password("SecureTestPassword123!")
        self.usuario.save(update_fields=["password"])
        datos_invalidos = {
            "username": self.usuario.username,
            "password": "incorrecta",
        }

        for _ in range(5):
            response = self.client.post("/accounts/login/", datos_invalidos)
            self.assertEqual(response.status_code, 200)

        response = self.client.post(
            "/accounts/login/",
            {
                "username": self.usuario.username,
                "password": "SecureTestPassword123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Demasiados intentos fallidos")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_limite_de_intentos_es_independiente_por_direccion_ip(self):
        self.usuario.set_password("SecureTestPassword123!")
        self.usuario.save(update_fields=["password"])
        datos_invalidos = {
            "username": self.usuario.username,
            "password": "incorrecta",
        }

        for _ in range(5):
            self.client.post("/accounts/login/", datos_invalidos)

        response = self.client.post(
            "/accounts/login/",
            {
                "username": self.usuario.username,
                "password": "SecureTestPassword123!",
            },
            REMOTE_ADDR="203.0.113.10",
        )

        self.assertRedirects(
            response,
            "/profile/",
            fetch_redirect_response=False,
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_muestra_control_accesible_para_ver_contrasena(self):
        response = self.client.get("/accounts/login/")

        self.assertContains(response, 'type="password"', html=False)
        self.assertContains(response, "data-password-toggle", html=False)
        self.assertContains(response, 'aria-label="Mostrar contraseña"', html=False)
        self.assertContains(response, 'aria-controls="id_password"', html=False)

    def test_cierre_de_sesion_requiere_post_y_invalida_la_sesion(self):
        self.client.force_login(self.usuario)

        get_response = self.client.get("/accounts/logout/")
        self.assertEqual(get_response.status_code, 405)
        self.assertTrue(get_response.wsgi_request.user.is_authenticated)

        response = self.client.post("/accounts/logout/")

        self.assertRedirects(response, "/")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_menu_muestra_cierre_de_sesion_protegido_con_csrf(self):
        self.client.force_login(self.usuario)

        response = self.client.get("/")

        self.assertContains(response, 'action="/accounts/logout/"', html=False)
        self.assertContains(response, "Cerrar sesión")
        self.assertContains(response, 'name="csrfmiddlewaretoken"', html=False)

    def test_cierre_de_sesion_rechaza_post_sin_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.usuario)

        response = client.post("/accounts/logout/")

        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_host_no_permitido_no_puede_iniciar_recuperacion_de_contrasena(self):
        response = self.client.get(
            "/accounts/password_reset/",
            HTTP_HOST="atacante.example",
        )

        self.assertEqual(response.status_code, 400)

    def test_correo_mal_formado_muestra_error_sin_exponer_cuentas(self):
        response = self.client.post(
            "/accounts/password_reset/",
            {"email": "no-es-un-correo"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertNotContains(response, "No se encontró una cuenta")

    def test_registro_administrativo_requiere_autenticacion(self):
        response = self.client.get("/usuario/registrar/")

        self.assertRedirects(
            response,
            "/accounts/login/?next=/usuario/registrar/",
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
            "/usuario/registrar/",
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
                "new_password1": "corta",
                "new_password2": "corta",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)

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

        response = self.client.get(set_password_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este enlace ya se utilizó o venció")
        self.assertNotContains(response, "Guardar nueva contraseña")

    def test_recuperacion_no_revela_si_el_correo_existe(self):
        known_response = self.client.post(
            "/accounts/password_reset/",
            {"email": self.usuario.email},
        )
        self.assertRedirects(
            known_response,
            "/accounts/password_reset/done/",
            fetch_redirect_response=False,
        )
        self.assertEqual(len(mail.outbox), 1)
        mail.outbox.clear()

        unknown_response = self.client.post(
            "/accounts/password_reset/",
            {"email": "no-existe@example.com"},
        )

        self.assertRedirects(
            unknown_response,
            "/accounts/password_reset/done/",
            fetch_redirect_response=False,
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_token_invalido_muestra_opcion_para_solicitar_otro(self):
        response = self.client.get("/accounts/reset/MQ/token-invalido/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este enlace ya se utilizó o venció")
        self.assertContains(response, "Solicitar otro enlace")
