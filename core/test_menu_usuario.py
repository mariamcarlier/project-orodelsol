"""Menú de la cuenta en la barra lateral del panel de administración."""

import re
import shutil
import tempfile
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

DATOS_BASE = {
    "tipo_documento": "CC",
    "fecha_nacimiento": date(1990, 1, 1),
    "telefono": "3001234567",
}


def crear_staff(username="empleada", documento="900000001", **extra):
    """Staff con permiso para ver el panel (accede a /panel-admin/)."""
    usuario = get_user_model().objects.create_superuser(
        username=username,
        password="clave-de-prueba",
        documento=documento,
        **DATOS_BASE,
        **extra,
    )
    return usuario


class MenuDeCuentaTests(TestCase):
    def setUp(self):
        self.usuario = crear_staff(first_name="Ana", last_name="López")
        self.client.force_login(self.usuario)
        self.url = reverse("core:admin_dashboard")

    def test_muestra_nombre_rol_e_iniciales_reales(self):
        response = self.client.get(self.url)

        self.assertContains(
            response, '<span class="sidebar-user__name">Ana</span>', html=True
        )
        self.assertContains(
            response,
            '<span class="sidebar-user__role">Administrador</span>',
            html=True,
        )
        # Sin foto, el avatar muestra las iniciales y no hay etiqueta <img>.
        self.assertContains(response, "AL")
        self.assertNotContains(response, "sidebar-user__photo")

    def test_el_menu_usa_details_nativo_sin_javascript_adicional(self):
        response = self.client.get(self.url)

        self.assertContains(response, '<details class="sidebar-user">')
        self.assertContains(response, '<summary class="sidebar-user__summary">')

    def test_las_acciones_llevan_a_las_rutas_reales_sin_duplicados(self):
        response = self.client.get(self.url)

        self.assertContains(response, "Ver tienda", count=1)
        self.assertContains(response, "Mi perfil", count=1)
        self.assertContains(response, "Cerrar sesión", count=1)
        self.assertContains(response, f'href="{reverse("usuarios:perfil")}"')
        self.assertContains(response, f'href="{reverse("core:inicio")}"')

    def test_no_repite_el_panel_de_administracion_en_el_menu_de_cuenta(self):
        """El menú solo existe dentro del panel; «Resumen» ya cubre ese destino."""
        html = self.client.get(self.url).content.decode()
        menu = html.split('<ul class="sidebar-user__menu">')[1].split("</ul>")[0]

        self.assertNotIn(reverse("core:admin_dashboard"), menu)

    def test_cerrar_sesion_es_un_formulario_post_con_csrf_y_la_ruta_central(self):
        html = self.client.get(self.url).content.decode()
        formulario = re.search(
            r'<form method="post" action="([^"]+)">(.*?)</form>',
            html.split('<ul class="sidebar-user__menu">')[1],
            flags=re.S,
        )

        self.assertIsNotNone(formulario)
        self.assertEqual(formulario.group(1), reverse("core:cerrar_sesion"))
        self.assertIn('name="csrfmiddlewaretoken"', formulario.group(2))
        # No se mantiene un segundo mecanismo de cierre (el del admin de Django).
        self.assertNotContains(
            self.client.get(self.url), reverse("admin:logout")
        )

    def test_cerrar_sesion_funciona_y_vuelve_al_inicio_de_sesion(self):
        response = self.client.post(reverse("core:cerrar_sesion"))

        self.assertRedirects(
            response, reverse("core:iniciar_sesion"), fetch_redirect_response=False
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_cerrar_sesion_no_se_acepta_por_get(self):
        response = self.client.get(reverse("core:cerrar_sesion"))

        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_el_enlace_de_perfil_antiguo_ya_no_esta_en_la_barra_superior(self):
        response = self.client.get(self.url)

        self.assertNotContains(response, "admin-profile-link")

    def test_la_barra_superior_conserva_el_boton_del_menu_movil(self):
        response = self.client.get(self.url)

        self.assertContains(response, '<header class="topbar">')
        self.assertContains(response, 'id="menuToggle"')
        self.assertContains(response, 'aria-controls="sidebar"')

    def test_se_muestra_el_rol_real_del_usuario_sin_inferir_permisos(self):
        """El rol es solo presentación: un staff con rol CLIENTE se ve como Cliente."""
        cliente_staff = crear_staff(
            username="staff_cliente",
            documento="900000002",
            first_name="Luis",
            last_name="Gómez",
        )
        get_user_model().objects.filter(pk=cliente_staff.pk).update(
            rol="CLIENTE", is_superuser=False
        )
        self.client.force_login(cliente_staff)
        # Sin permisos de vista no hay recursos, pero el panel sigue siendo de staff.
        response = self.client.get(reverse("core:admin_dashboard"))

        self.assertContains(
            response,
            '<span class="sidebar-user__role">Cliente</span>',
            html=True,
        )


class MenuDeCuentaFotoTests(TestCase):
    def setUp(self):
        self.carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.carpeta, ignore_errors=True)

    def test_con_foto_muestra_la_imagen_y_con_alt_vacio_porque_es_decorativa(self):
        with override_settings(MEDIA_ROOT=self.carpeta):
            usuario = crear_staff(first_name="Ana", last_name="López")
            usuario.foto.save(
                "ana.png", SimpleUploadedFile("ana.png", b"no-importa"), save=True
            )
            self.client.force_login(usuario)

            response = self.client.get(reverse("core:admin_dashboard"))

        self.assertContains(response, "sidebar-user__photo")
        self.assertContains(response, 'alt=""')
        self.assertContains(response, usuario.foto.url)


class MenuDeCuentaAccesoTests(TestCase):
    def test_un_anonimo_no_ve_el_panel_ni_su_menu(self):
        response = self.client.get(reverse("core:admin_dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("sidebar-user", response.content.decode())

    def test_un_usuario_sin_is_staff_no_entra_aunque_tenga_rol_admin(self):
        usuario = get_user_model().objects.create_user(
            username="solo_rol",
            password="clave-de-prueba",
            documento="900000003",
            rol="ADMIN",
            **DATOS_BASE,
        )
        self.client.force_login(usuario)

        response = self.client.get(reverse("core:admin_dashboard"))

        self.assertEqual(response.status_code, 302)
