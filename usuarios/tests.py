from datetime import date
import re
from unittest.mock import patch

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
        self.assertContains(response, 'action="/logout/"', html=False)
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
            "/login/?next=/usuario/perfil/",
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
            "/usuario/perfil/",
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
            "/usuario/perfil/",
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

        self.assertRedirects(response, "/login/")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_menu_muestra_cierre_de_sesion_protegido_con_csrf(self):
        self.client.force_login(self.usuario)

        response = self.client.get("/")

        self.assertContains(response, 'action="/logout/"', html=False)
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
            "/login/?next=/usuario/registrar/",
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


class TipoDeCuentaTests(TestCase):
    """El perfil muestra la etiqueta correcta sin alterar los permisos."""

    def crear(self, username, documento, **extra):
        datos = {
            "password": "ClaveSegura123!",
            "first_name": "Prueba",
            "last_name": "Cuenta",
            "tipo_documento": "CC",
            "documento": documento,
            "fecha_nacimiento": date(1990, 1, 1),
            "telefono": "3001234567",
        }
        datos.update(extra)
        return get_user_model().objects.create_user(username=username, **datos)

    def etiqueta_en_perfil(self, usuario):
        self.client.force_login(usuario)
        response = self.client.get("/usuario/perfil/")
        self.assertEqual(response.status_code, 200)
        return response

    def test_superusuario_creado_con_createsuperuser_se_muestra_administrador(self):
        superusuario = get_user_model().objects.create_superuser(
            username="super",
            password="ClaveSegura123!",
            first_name="Super",
            last_name="Usuario",
            tipo_documento="CC",
            documento="111",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
        )
        self.assertEqual(superusuario.rol, "CLIENTE")  # el rol no se toca

        response = self.etiqueta_en_perfil(superusuario)

        self.assertContains(response, "<dd>Administrador</dd>", html=True)

    def test_rol_admin_se_muestra_administrador(self):
        response = self.etiqueta_en_perfil(self.crear("adm", "222", rol="ADMIN"))

        self.assertContains(response, "<dd>Administrador</dd>", html=True)

    def test_mayorista_se_muestra_mayorista(self):
        response = self.etiqueta_en_perfil(self.crear("may", "333", rol="MAYORISTA"))

        self.assertContains(response, "<dd>Mayorista</dd>", html=True)

    def test_cliente_se_muestra_cliente(self):
        response = self.etiqueta_en_perfil(self.crear("cli", "444"))

        self.assertContains(response, "<dd>Cliente</dd>", html=True)

    def test_personal_staff_con_rol_cliente_sigue_siendo_cliente(self):
        staff = self.crear("staff", "555", is_staff=True)

        self.assertEqual(staff.tipo_cuenta, "Cliente")

    def test_la_etiqueta_coincide_con_la_regla_de_es_administrador(self):
        from .views import es_administrador

        for rol in ("ADMIN", "MAYORISTA", "CLIENTE"):
            for superusuario in (False, True):
                with self.subTest(rol=rol, superusuario=superusuario):
                    usuario = get_user_model()(rol=rol, is_superuser=superusuario)
                    self.assertEqual(
                        es_administrador(usuario),
                        usuario.tipo_cuenta == "Administrador",
                    )

    def test_ver_el_perfil_no_cambia_roles_ni_permisos(self):
        superusuario = self.crear("super2", "666", is_staff=True, is_superuser=True)

        self.etiqueta_en_perfil(superusuario)

        superusuario.refresh_from_db()
        self.assertEqual(superusuario.rol, "CLIENTE")
        self.assertTrue(superusuario.is_staff)
        self.assertTrue(superusuario.is_superuser)

    def test_el_acceso_al_panel_sigue_dependiendo_de_is_staff(self):
        cliente = self.crear("cli2", "777")
        rol_admin_sin_staff = self.crear("adm2", "888", rol="ADMIN")
        superusuario = self.crear("super3", "999", is_staff=True, is_superuser=True)

        for usuario, esperado in (
            (cliente, 302),
            (rol_admin_sin_staff, 302),
            (superusuario, 200),
        ):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                self.assertEqual(self.client.get("/panel-admin/").status_code, esperado)

    def test_perfil_carga_su_hoja_de_estilos_una_sola_vez(self):
        response = self.etiqueta_en_perfil(self.crear("cli3", "1010"))

        self.assertContains(response, "css/perfil.css", count=1)


class SaludoBienvenidaTests(TestCase):
    """El saludo se calcula en Python y nunca muestra None ni espacios sobrantes."""

    def usuario(self, **datos):
        datos.setdefault("username", "mariam01")
        return get_user_model()(**datos)

    def test_usa_el_nombre_tal_como_esta_guardado(self):
        self.assertEqual(self.usuario(first_name="Mariam").nombre_visible, "Mariam")

    def test_conserva_los_nombres_compuestos_y_los_acentos(self):
        usuario = self.usuario(first_name="María José")

        self.assertEqual(usuario.nombre_visible, "María José")

    def test_quita_espacios_sobrantes_al_inicio_al_final_y_en_medio(self):
        usuario = self.usuario(first_name="  Luis   Enrique  ")

        self.assertEqual(usuario.nombre_visible, "Luis Enrique")

    def test_si_el_nombre_esta_vacio_usa_el_nombre_de_usuario(self):
        self.assertEqual(self.usuario(first_name="").nombre_visible, "mariam01")

    def test_si_el_nombre_solo_tiene_espacios_usa_el_nombre_de_usuario(self):
        self.assertEqual(self.usuario(first_name="   ").nombre_visible, "mariam01")

    def test_si_el_nombre_es_none_usa_el_nombre_de_usuario(self):
        self.assertEqual(self.usuario(first_name=None).nombre_visible, "mariam01")

    def test_el_saludo_es_neutro(self):
        usuario = self.usuario(first_name="Mariam")

        self.assertEqual(usuario.saludo_bienvenida, "Te damos la bienvenida, Mariam")

    def test_el_saludo_nunca_contiene_none_ni_espacios_dobles(self):
        for nombre in ("Mariam", "", "   ", None, "  Luis   Enrique "):
            with self.subTest(nombre=nombre):
                saludo = self.usuario(first_name=nombre).saludo_bienvenida

                self.assertNotIn("None", saludo)
                self.assertEqual(saludo, " ".join(saludo.split()))

    def test_la_propiedad_no_altera_otros_caracteres(self):
        # El escapado de HTML es responsabilidad de la plantilla, no del modelo.
        usuario = self.usuario(first_name="<b>Eva</b>")

        self.assertEqual(usuario.nombre_visible, "<b>Eva</b>")


class CabeceraDeCuentaTests(TestCase):
    """La cabecera de bienvenida muestra datos reales y la imagen es opcional y segura."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="cli",
            password="ClaveSegura123!",
            first_name="Mariam",
            last_name="Alvarado",
            tipo_documento="CC",
            documento="1",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
        )
        self.client.force_login(self.usuario)

    def pagina(self):
        return self.client.get("/usuario/perfil/")

    def test_muestra_el_saludo_con_el_nombre_real(self):
        self.assertContains(self.pagina(), "Te damos la bienvenida, Mariam")

    def test_el_saludo_es_el_unico_h1_y_mi_perfil_pasa_a_h2(self):
        response = self.pagina()

        self.assertContains(response, "<h1", count=1)
        self.assertContains(
            response,
            '<h1 id="account-hero-title" class="account-hero__title">'
            "Te damos la bienvenida, Mariam</h1>",
        )
        self.assertContains(response, '<h2 id="profile-title"')

    def test_sin_nombre_saluda_con_el_nombre_de_usuario(self):
        self.usuario.first_name = ""
        self.usuario.save()

        self.assertContains(self.pagina(), "Te damos la bienvenida, cli")

    def test_el_nombre_se_escapa_en_la_cabecera(self):
        self.usuario.first_name = "<b>Eva</b>"
        self.usuario.save()

        response = self.pagina()

        self.assertNotContains(response, "<b>Eva</b>")
        self.assertContains(response, "Te damos la bienvenida, &lt;b&gt;Eva&lt;/b&gt;")

    def test_sin_imagen_solo_se_ve_el_degradado(self):
        response = self.pagina()

        self.assertContains(response, 'class="account-hero"')
        self.assertNotContains(response, "account-hero--con-imagen")
        self.assertNotContains(response, "account-hero__image")

    def test_con_imagen_se_muestra_como_decorativa(self):
        with patch("usuarios.views.imagen_banner_cuenta", return_value="/media/banner.webp"):
            response = self.pagina()

        self.assertContains(
            response,
            '<img class="account-hero__image" src="/media/banner.webp" alt=""',
        )
        self.assertContains(response, "account-hero--con-imagen")

    def test_la_url_de_la_imagen_no_puede_inyectar_html(self):
        malicioso = '"><script>alert(1)</script>'
        with patch("usuarios.views.imagen_banner_cuenta", return_value=malicioso):
            response = self.pagina()

        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_hoy_no_hay_imagen_administrable(self):
        from .views import imagen_banner_cuenta

        self.assertIsNone(imagen_banner_cuenta(self.usuario))

    def test_el_perfil_sigue_mostrando_sus_datos_y_la_foto_inicial(self):
        response = self.pagina()

        self.assertContains(response, "<dd>Mariam</dd>", html=True)
        self.assertContains(response, "<dd>Cliente</dd>", html=True)
        self.assertContains(response, 'class="profile-card__photo"')