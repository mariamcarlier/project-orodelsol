from django.test import TestCase
from django.urls import reverse


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
