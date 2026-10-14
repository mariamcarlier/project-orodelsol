from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from configuracion.models import CostoEnvio, Impuesto, Moneda, Idioma, ParametroGeneral

Usuario = get_user_model()


class LegacyConfigurationRedirectTests(TestCase):
    def test_old_configuration_routes_redirect_to_dashboard_sections(self):
        routes = (
            ("configuracion:configuracion_home", "parametros"),
            ("configuracion:parametros", "parametros"),
            ("configuracion:impuesto_list", "impuestos"),
            ("configuracion:impuesto_create", "impuestos"),
            ("configuracion:moneda_list", "monedas"),
            ("configuracion:moneda_create", "monedas"),
            ("configuracion:idioma_list", "idiomas"),
            ("configuracion:idioma_create", "idiomas"),
        )

        for old_route, section in routes:
            with self.subTest(old_route=old_route):
                response = self.client.get(reverse(old_route))

                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    response["Location"],
                    reverse("core:admin_section", kwargs={"seccion": section}),
                )

    def test_post_a_una_ruta_antigua_no_descarta_silenciosamente_los_datos(self):
        response = self.client.post(reverse("configuracion:impuesto_create"), {
            "nombre": "IVA",
            "tasa": "19.00",
        })

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET, HEAD")


class CostoEnvioCFG05Tests(TestCase):
    """Pruebas de la historia JODS-194: CFG-05 — Costos de envío."""

    def setUp(self):
        self.admin_user = Usuario.objects.create_superuser(
            username="admin_costos_envio",
            password="password123",
            email="admin-envios@example.com",
            first_name="Admin",
            last_name="Envíos",
            tipo_documento="CC",
            documento="987654321",
            fecha_nacimiento="1990-01-01",
            telefono="3001234567",
        )
        self.client.force_login(self.admin_user)
        self.url = reverse(
            "core:admin_section",
            kwargs={"seccion": "costos_envio"},
        )

    def test_admin_puede_acceder_al_panel_costos_envio(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "admin_custom/section.html",
        )
        self.assertContains(response, "Costos de envío")

    def test_creacion_exitosa_de_tarifa_valida(self):
        response = self.client.post(self.url, {
            "recurso": "costos_envio",
            "accion": "create",
            "costos_envio-nuevo-ciudad": "Bogotá",
            "costos_envio-nuevo-departamento": "Cundinamarca",
            "costos_envio-nuevo-precio": "12000.00",
            "costos_envio-nuevo-tiempo_entrega": "2 a 4 días hábiles",
            "costos_envio-nuevo-activo": "on",
        })
        self.assertRedirects(response, f"{self.url}#registros")
        tarifa = CostoEnvio.objects.get(
            ciudad="Bogotá",
            departamento="Cundinamarca",
        )
        self.assertEqual(tarifa.precio, Decimal("12000.00"))
        self.assertTrue(tarifa.activo)

    def test_rechaza_tarifa_con_precio_negativo(self):
        response = self.client.post(self.url, {
            "recurso": "costos_envio",
            "accion": "create",
            "costos_envio-nuevo-ciudad": "Tunja",
            "costos_envio-nuevo-departamento": "Boyacá",
            "costos_envio-nuevo-precio": "-100.00",
            "costos_envio-nuevo-tiempo_entrega": "1 a 2 días hábiles",
            "costos_envio-nuevo-activo": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CostoEnvio.objects.count(), 0)
        self.assertContains(response, "El costo de envío no puede ser negativo.")

    def test_rechaza_tarifa_duplicada_para_ciudad_y_departamento(self):
        CostoEnvio.objects.create(
            ciudad="Bogotá",
            departamento="Cundinamarca",
            precio=Decimal("12000.00"),
        )
        response = self.client.post(self.url, {
            "recurso": "costos_envio",
            "accion": "create",
            "costos_envio-nuevo-ciudad": "Bogotá",
            "costos_envio-nuevo-departamento": "Cundinamarca",
            "costos_envio-nuevo-precio": "15000.00",
            "costos_envio-nuevo-tiempo_entrega": "3 a 5 días hábiles",
            "costos_envio-nuevo-activo": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CostoEnvio.objects.count(), 1)
        self.assertTrue(response.context["recurso"]["crear_formulario"].errors)

    def test_accion_masiva_activa_y_desactiva_tarifas(self):
        tarifa = CostoEnvio.objects.create(
            ciudad="Sogamoso",
            departamento="Boyacá",
            precio=Decimal("9000.00"),
            activo=True,
        )
        response = self.client.post(self.url, {
            "recurso": "costos_envio",
            "accion": "bulk",
            "estado": "0",
            "registros": [str(tarifa.pk)],
        })
        self.assertRedirects(response, f"{self.url}#registros")
        tarifa.refresh_from_db()
        self.assertFalse(tarifa.activo)

        self.client.post(self.url, {
            "recurso": "costos_envio",
            "accion": "bulk",
            "estado": "1",
            "registros": [str(tarifa.pk)],
        })
        tarifa.refresh_from_db()
        self.assertTrue(tarifa.activo)