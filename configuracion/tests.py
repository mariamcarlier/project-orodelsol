

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from configuracion.models import CostoEnvio, Idioma, Impuesto, Moneda, ParametroGeneral

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
        
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from configuracion.models import (
    CostoEnvio,
    Idioma,
    Impuesto,
    MetodoPago,
    Moneda,
    ParametroGeneral,
    PoliticaComercial,
)


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


class MetodoPagoCFG06Tests(TestCase):
    """Pruebas de la historia JODS-195: CFG-06 — Medios de pago."""

    def setUp(self):
        self.admin_user = Usuario.objects.create_superuser(
            username="admin_medios_pago",
            password="password123",
            email="admin-pagos@example.com",
            first_name="Admin",
            last_name="Pagos",
            tipo_documento="CC",
            documento="987654322",
            fecha_nacimiento="1990-01-01",
            telefono="3001234568",
        )
        self.cliente_user = Usuario.objects.create_user(
            username="cliente_regular",
            password="password123",
            email="cliente@example.com",
            first_name="Cliente",
            last_name="Regular",
            tipo_documento="CC",
            documento="1122334455",
            fecha_nacimiento="1995-05-05",
            telefono="3119876543",
            rol="CLIENTE",
        )
        self.staff_sin_permiso = Usuario.objects.create_user(
            username="staff_sin_permiso",
            password="password123",
            email="staff@example.com",
            first_name="Staff",
            last_name="SinPermiso",
            tipo_documento="CC",
            documento="9988776655",
            fecha_nacimiento="1992-02-02",
            telefono="3009876543",
            is_staff=True,
        )
        self.client.force_login(self.admin_user)
        self.url = reverse(
            "core:admin_section",
            kwargs={"seccion": "metodos_pago"},
        )

    def test_admin_puede_acceder_al_panel_metodos_pago(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_custom/section.html")
        self.assertContains(response, "Medios de pago")

    def test_cliente_no_staff_es_redirigido_al_login(self):
        self.client.force_login(self.cliente_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_staff_sin_permiso_de_modelo_es_denegado(self):
        self.client.force_login(self.staff_sin_permiso)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_creacion_exitosa_de_transferencia_con_comprobante(self):
        response = self.client.post(self.url, {
            "recurso": "metodos_pago",
            "accion": "create",
            "metodos_pago-nuevo-nombre": "Bancolombia Transferencia",
            "metodos_pago-nuevo-tipo": "TRANSFERENCIA",
            "metodos_pago-nuevo-banco": "Bancolombia",
            "metodos_pago-nuevo-tipo_cuenta": "AHORROS",
            "metodos_pago-nuevo-numero_cuenta": "123-456789-01",
            "metodos_pago-nuevo-titular": "Joyas Oro del Sol S.A.S.",
            "metodos_pago-nuevo-documento_titular": "900.123.456-7",
            "metodos_pago-nuevo-instrucciones": (
                "Realiza la transferencia a la cuenta de ahorros y adjunta la captura o comprobante."
            ),
            "metodos_pago-nuevo-activo": "on",
            "metodos_pago-nuevo-orden": "1",
        })
        self.assertRedirects(response, f"{self.url}#registros")
        metodo = MetodoPago.objects.get(nombre="Bancolombia Transferencia")
        self.assertEqual(metodo.tipo, "TRANSFERENCIA")
        self.assertEqual(metodo.banco, "Bancolombia")
        self.assertEqual(metodo.numero_cuenta, "123-456789-01")
        self.assertEqual(metodo.titular, "Joyas Oro del Sol S.A.S.")
        self.assertTrue(metodo.activo)
        self.assertEqual(metodo.orden, 1)

    def test_creacion_exitosa_de_billetera_digital_nequi(self):
        response = self.client.post(self.url, {
            "recurso": "metodos_pago",
            "accion": "create",
            "metodos_pago-nuevo-nombre": "Nequi",
            "metodos_pago-nuevo-tipo": "NEQUI",
            "metodos_pago-nuevo-tipo_cuenta": "BILLETERA",
            "metodos_pago-nuevo-numero_cuenta": "3001234567",
            "metodos_pago-nuevo-titular": "Oro del Sol",
            "metodos_pago-nuevo-instrucciones": "Envía el dinero a la línea Nequi y sube tu comprobante.",
            "metodos_pago-nuevo-activo": "on",
            "metodos_pago-nuevo-orden": "2",
        })
        self.assertRedirects(response, f"{self.url}#registros")
        metodo = MetodoPago.objects.get(nombre="Nequi")
        self.assertEqual(metodo.banco, "Nequi")
        self.assertTrue(metodo.activo)

    def test_rechaza_transferencia_sin_cuenta_ni_titular(self):
        response = self.client.post(self.url, {
            "recurso": "metodos_pago",
            "accion": "create",
            "metodos_pago-nuevo-nombre": "Transferencia Incompleta",
            "metodos_pago-nuevo-tipo": "TRANSFERENCIA",
            "metodos_pago-nuevo-banco": "Davivienda",
            "metodos_pago-nuevo-tipo_cuenta": "AHORROS",
            "metodos_pago-nuevo-numero_cuenta": "",
            "metodos_pago-nuevo-titular": "",
            "metodos_pago-nuevo-instrucciones": "Instrucciones de prueba",
            "metodos_pago-nuevo-activo": "on",
            "metodos_pago-nuevo-orden": "1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MetodoPago.objects.count(), 0)
        formulario = response.context["recurso"]["crear_formulario"]
        self.assertIn("numero_cuenta", formulario.errors)
        self.assertIn("titular", formulario.errors)

    def test_rechaza_nombre_duplicado(self):
        MetodoPago.objects.create(
            nombre="Daviplata",
            tipo="DAVIPLATA",
            banco="Daviplata",
            numero_cuenta="3009998877",
            titular="Oro del Sol",
            instrucciones="Paga por Daviplata",
        )
        response = self.client.post(self.url, {
            "recurso": "metodos_pago",
            "accion": "create",
            "metodos_pago-nuevo-nombre": "Daviplata",
            "metodos_pago-nuevo-tipo": "DAVIPLATA",
            "metodos_pago-nuevo-numero_cuenta": "3009998877",
            "metodos_pago-nuevo-titular": "Oro del Sol",
            "metodos_pago-nuevo-instrucciones": "Otra descripción",
            "metodos_pago-nuevo-activo": "on",
            "metodos_pago-nuevo-orden": "1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MetodoPago.objects.count(), 1)
        formulario = response.context["recurso"]["crear_formulario"]
        self.assertIn("nombre", formulario.errors)

    def test_edicion_metodo_pago(self):
        metodo = MetodoPago.objects.create(
            nombre="Bancolombia Ahorros",
            tipo="TRANSFERENCIA",
            banco="Bancolombia",
            numero_cuenta="111-222-333",
            titular="Oro del Sol",
            instrucciones="Instrucción previa",
            activo=True,
        )
        response = self.client.post(self.url, {
            "recurso": "metodos_pago",
            "accion": "edit",
            "registro": str(metodo.pk),
            f"metodos_pago-{metodo.pk}-nombre": "Bancolombia Ahorros",
            f"metodos_pago-{metodo.pk}-tipo": "TRANSFERENCIA",
            f"metodos_pago-{metodo.pk}-banco": "Bancolombia",
            f"metodos_pago-{metodo.pk}-tipo_cuenta": "AHORROS",
            f"metodos_pago-{metodo.pk}-numero_cuenta": "111-222-333",
            f"metodos_pago-{metodo.pk}-titular": "Oro del Sol S.A.S.",
            f"metodos_pago-{metodo.pk}-documento_titular": "900.123.456-7",
            f"metodos_pago-{metodo.pk}-instrucciones": "Nueva instrucción actualizada con soporte de WhatsApp",
            f"metodos_pago-{metodo.pk}-orden": "0",
            # Sin activo -> se desmarca
        })
        self.assertRedirects(response, f"{self.url}#registros")
        metodo.refresh_from_db()
        self.assertEqual(metodo.titular, "Oro del Sol S.A.S.")
        self.assertEqual(metodo.instrucciones, "Nueva instrucción actualizada con soporte de WhatsApp")
        self.assertFalse(metodo.activo)

    def test_accion_masiva_activa_y_desactiva_metodos(self):
        metodo = MetodoPago.objects.create(
            nombre="Efectivo Contraentrega",
            tipo="EFECTIVO",
            instrucciones="Pago en efectivo al recibir",
            activo=True,
        )
        response = self.client.post(self.url, {
            "recurso": "metodos_pago",
            "accion": "bulk",
            "estado": "0",
            "registros": [str(metodo.pk)],
        })
        self.assertRedirects(response, f"{self.url}#registros")
        metodo.refresh_from_db()
        self.assertFalse(metodo.activo)

        self.client.post(self.url, {
            "recurso": "metodos_pago",
            "accion": "bulk",
            "estado": "1",
            "registros": [str(metodo.pk)],
        })
        metodo.refresh_from_db()
        self.assertTrue(metodo.activo)

    def test_rutas_legadas_metodos_pago_redirigen_a_panel(self):
        response_list = self.client.get(reverse("configuracion:metodo_pago_list"))
        self.assertEqual(response_list.status_code, 302)
        self.assertEqual(response_list["Location"], self.url)

        response_create = self.client.get(reverse("configuracion:metodo_pago_create"))
        self.assertEqual(response_create.status_code, 302)
        self.assertEqual(response_create["Location"], self.url)


class PoliticaComercialCFG08Tests(TestCase):
    """Pruebas de la historia JODS-197: CFG-08 — Políticas comerciales."""

    def setUp(self):
        self.admin_user = Usuario.objects.create_superuser(
            username="admin_politicas",
            password="password123",
            email="admin-politicas@example.com",
            first_name="Admin",
            last_name="Politicas",
            tipo_documento="CC",
            documento="987654323",
            fecha_nacimiento="1990-01-01",
            telefono="3001234569",
        )
        self.cliente_user = Usuario.objects.create_user(
            username="cliente_politica",
            password="password123",
            email="cliente-pol@example.com",
            first_name="Cliente",
            last_name="B2C",
            tipo_documento="CC",
            documento="1122334456",
            fecha_nacimiento="1995-05-05",
            telefono="3119876544",
            rol="CLIENTE",
        )
        self.mayorista_user = Usuario.objects.create_user(
            username="mayorista_politica",
            password="password123",
            email="mayorista-pol@example.com",
            first_name="Mayorista",
            last_name="B2B",
            tipo_documento="CC",
            documento="1122334457",
            fecha_nacimiento="1988-08-08",
            telefono="3119876545",
            rol="MAYORISTA",
        )
        self.staff_sin_permiso = Usuario.objects.create_user(
            username="staff_sin_permiso_pol",
            password="password123",
            email="staff-pol@example.com",
            first_name="Staff",
            last_name="SinPermiso",
            tipo_documento="CC",
            documento="9988776656",
            fecha_nacimiento="1992-02-02",
            telefono="3009876544",
            is_staff=True,
        )
        self.client.force_login(self.admin_user)
        self.url = reverse(
            "core:admin_section",
            kwargs={"seccion": "politicas_comerciales"},
        )

    def test_admin_puede_acceder_al_panel_politicas_comerciales(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_custom/section.html")
        self.assertContains(response, "Políticas comerciales")

    def test_cliente_no_staff_es_redirigido_al_login(self):
        self.client.force_login(self.cliente_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_staff_sin_permiso_de_modelo_es_denegado(self):
        self.client.force_login(self.staff_sin_permiso)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_edicion_exitosa_politicas_comerciales_singleton(self):
        politica = PoliticaComercial.get_solo()
        response = self.client.post(self.url, {
            "recurso": "politicas_comerciales",
            "accion": "edit",
            "registro": str(politica.pk),
            f"politicas_comerciales-{politica.pk}-monto_minimo_compra_b2c": "50000.00",
            f"politicas_comerciales-{politica.pk}-monto_minimo_compra_b2b": "200000.00",
            f"politicas_comerciales-{politica.pk}-monto_minimo_envio_gratis": "150000.00",
            f"politicas_comerciales-{politica.pk}-tiempo_reserva_carrito_minutos": "45",
            f"politicas_comerciales-{politica.pk}-vigencia_cupones_dias": "15",
        })
        self.assertRedirects(response, f"{self.url}#registros")
        self.assertEqual(PoliticaComercial.objects.count(), 1)
        politica.refresh_from_db()
        self.assertEqual(politica.monto_minimo_compra_b2c, Decimal("50000.00"))
        self.assertEqual(politica.monto_minimo_compra_b2b, Decimal("200000.00"))
        self.assertEqual(politica.monto_minimo_envio_gratis, Decimal("150000.00"))
        self.assertEqual(politica.tiempo_reserva_carrito_minutos, 45)
        self.assertEqual(politica.vigencia_cupones_dias, 15)
        self.assertEqual(politica.actualizado_por, self.admin_user)

    def test_rechaza_montos_negativos(self):
        politica = PoliticaComercial.get_solo()
        response = self.client.post(self.url, {
            "recurso": "politicas_comerciales",
            "accion": "edit",
            "registro": str(politica.pk),
            f"politicas_comerciales-{politica.pk}-monto_minimo_compra_b2c": "-500.00",
            f"politicas_comerciales-{politica.pk}-monto_minimo_compra_b2b": "-1000.00",
            f"politicas_comerciales-{politica.pk}-monto_minimo_envio_gratis": "-10.00",
            f"politicas_comerciales-{politica.pk}-tiempo_reserva_carrito_minutos": "30",
            f"politicas_comerciales-{politica.pk}-vigencia_cupones_dias": "30",
        })
        self.assertEqual(response.status_code, 200)
        formulario = response.context["recurso"]["filas"][0]["formulario"]
        self.assertIn("monto_minimo_compra_b2c", formulario.errors)
        self.assertIn("monto_minimo_compra_b2b", formulario.errors)
        self.assertIn("monto_minimo_envio_gratis", formulario.errors)

    def test_rechaza_tiempos_invalidos(self):
        politica = PoliticaComercial.get_solo()
        response = self.client.post(self.url, {
            "recurso": "politicas_comerciales",
            "accion": "edit",
            "registro": str(politica.pk),
            f"politicas_comerciales-{politica.pk}-monto_minimo_compra_b2c": "0.00",
            f"politicas_comerciales-{politica.pk}-monto_minimo_compra_b2b": "0.00",
            f"politicas_comerciales-{politica.pk}-monto_minimo_envio_gratis": "0.00",
            f"politicas_comerciales-{politica.pk}-tiempo_reserva_carrito_minutos": "0",
            f"politicas_comerciales-{politica.pk}-vigencia_cupones_dias": "0",
        })
        self.assertEqual(response.status_code, 200)
        formulario = response.context["recurso"]["filas"][0]["formulario"]
        self.assertIn("tiempo_reserva_carrito_minutos", formulario.errors)
        self.assertIn("vigencia_cupones_dias", formulario.errors)

    def test_metodo_centralizado_validar_monto_minimo_b2b_y_b2c(self):
        politica = PoliticaComercial.get_solo()
        politica.monto_minimo_compra_b2c = Decimal("50000.00")
        politica.monto_minimo_compra_b2b = Decimal("200000.00")
        politica.save()

        # Validación cliente regular (B2C)
        valido_b2c, requerido_b2c = politica.validar_monto_minimo(self.cliente_user, Decimal("30000.00"))
        self.assertFalse(valido_b2c)
        self.assertEqual(requerido_b2c, Decimal("50000.00"))

        valido_b2c_ok, _ = politica.validar_monto_minimo(self.cliente_user, Decimal("50000.00"))
        self.assertTrue(valido_b2c_ok)

        # Validación mayorista (B2B)
        valido_b2b, requerido_b2b = politica.validar_monto_minimo(self.mayorista_user, Decimal("150000.00"))
        self.assertFalse(valido_b2b)
        self.assertEqual(requerido_b2b, Decimal("200000.00"))

        valido_b2b_ok, _ = politica.validar_monto_minimo(self.mayorista_user, Decimal("250000.00"))
        self.assertTrue(valido_b2b_ok)

    def test_metodo_centralizado_aplica_envio_gratis(self):
        politica = PoliticaComercial.get_solo()
        politica.monto_minimo_envio_gratis = Decimal("150000.00")
        politica.save()

        self.assertFalse(politica.aplica_envio_gratis(Decimal("100000.00")))
        self.assertTrue(politica.aplica_envio_gratis(Decimal("150000.00")))
        self.assertTrue(politica.aplica_envio_gratis(Decimal("180000.00")))

        # Con monto 0 queda desactivado
        politica.monto_minimo_envio_gratis = Decimal("0.00")
        politica.save()
        self.assertFalse(politica.aplica_envio_gratis(Decimal("500000.00")))

    def test_ruta_legada_politicas_comerciales_redirige_a_panel(self):
        response = self.client.get(reverse("configuracion:politica_comercial_detail"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], self.url)



from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from configuracion.models import (
    CostoEnvio,
    Idioma,
    Impuesto,
    MetodoPago,
    Moneda,
    ParametroGeneral,
    PlantillaDocumento,
    PoliticaComercial,
)
from configuracion.services import obtener_plantilla_vigente


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


class MetodoPagoCFG06Tests(TestCase):
    """Pruebas de la historia JODS-195: CFG-06 — Medios de pago."""

    def setUp(self):
        self.admin_user = Usuario.objects.create_superuser(
            username="admin_medios_pago",
            password="password123",
            email="admin-pagos@example.com",
            first_name="Admin",
            last_name="Pagos",
            tipo_documento="CC",
            documento="987654322",
            fecha_nacimiento="1990-01-01",
            telefono="3001234568",
        )
        self.cliente_user = Usuario.objects.create_user(
            username="cliente_regular",
            password="password123",
            email="cliente@example.com",
            first_name="Cliente",
            last_name="Regular",
            tipo_documento="CC",
            documento="1122334455",
            fecha_nacimiento="1995-05-05",
            telefono="3119876543",
            rol="CLIENTE",
        )
        self.staff_sin_permiso = Usuario.objects.create_user(
            username="staff_sin_permiso",
            password="password123",
            email="staff@example.com",
            first_name="Staff",
            last_name="SinPermiso",
            tipo_documento="CC",
            documento="9988776655",
            fecha_nacimiento="1992-02-02",
            telefono="3009876543",
            is_staff=True,
        )
        self.client.force_login(self.admin_user)
        self.url = reverse(
            "core:admin_section",
            kwargs={"seccion": "metodos_pago"},
        )

    def test_admin_puede_acceder_al_panel_metodos_pago(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_custom/section.html")
        self.assertContains(response, "Medios de pago")

    def test_cliente_no_staff_es_redirigido_al_login(self):
        self.client.force_login(self.cliente_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_staff_sin_permiso_de_modelo_es_denegado(self):
        self.client.force_login(self.staff_sin_permiso)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_creacion_exitosa_de_transferencia_con_comprobante(self):
        response = self.client.post(self.url, {
            "recurso": "metodos_pago",
            "accion": "create",
            "metodos_pago-nuevo-nombre": "Bancolombia Transferencia",
            "metodos_pago-nuevo-tipo": "TRANSFERENCIA",
            "metodos_pago-nuevo-banco": "Bancolombia",
            "metodos_pago-nuevo-tipo_cuenta": "AHORROS",
            "metodos_pago-nuevo-numero_cuenta": "123-456789-01",
            "metodos_pago-nuevo-titular": "Joyas Oro del Sol S.A.S.",
            "metodos_pago-nuevo-documento_titular": "900.123.456-7",
            "metodos_pago-nuevo-instrucciones": (
                "Realiza la transferencia a la cuenta de ahorros y adjunta la captura o comprobante."
            ),
            "metodos_pago-nuevo-activo": "on",
            "metodos_pago-nuevo-orden": "1",
        })
        self.assertRedirects(response, f"{self.url}#registros")
        metodo = MetodoPago.objects.get(nombre="Bancolombia Transferencia")
        self.assertEqual(metodo.tipo, "TRANSFERENCIA")
        self.assertEqual(metodo.banco, "Bancolombia")
        self.assertEqual(metodo.numero_cuenta, "123-456789-01")
        self.assertEqual(metodo.titular, "Joyas Oro del Sol S.A.S.")
        self.assertTrue(metodo.activo)
        self.assertEqual(metodo.orden, 1)

    def test_creacion_exitosa_de_billetera_digital_nequi(self):
        response = self.client.post(self.url, {
            "recurso": "metodos_pago",
            "accion": "create",
            "metodos_pago-nuevo-nombre": "Nequi",
            "metodos_pago-nuevo-tipo": "NEQUI",
            "metodos_pago-nuevo-tipo_cuenta": "BILLETERA",
            "metodos_pago-nuevo-numero_cuenta": "3001234567",
            "metodos_pago-nuevo-titular": "Oro del Sol",
            "metodos_pago-nuevo-instrucciones": "Envía el dinero a la línea Nequi y sube tu comprobante.",
            "metodos_pago-nuevo-activo": "on",
            "metodos_pago-nuevo-orden": "2",
        })
        self.assertRedirects(response, f"{self.url}#registros")
        metodo = MetodoPago.objects.get(nombre="Nequi")
        self.assertEqual(metodo.banco, "Nequi")
        self.assertTrue(metodo.activo)

    def test_rechaza_transferencia_sin_cuenta_ni_titular(self):
        response = self.client.post(self.url, {
            "recurso": "metodos_pago",
            "accion": "create",
            "metodos_pago-nuevo-nombre": "Transferencia Incompleta",
            "metodos_pago-nuevo-tipo": "TRANSFERENCIA",
            "metodos_pago-nuevo-banco": "Davivienda",
            "metodos_pago-nuevo-tipo_cuenta": "AHORROS",
            "metodos_pago-nuevo-numero_cuenta": "",
            "metodos_pago-nuevo-titular": "",
            "metodos_pago-nuevo-instrucciones": "Instrucciones de prueba",
            "metodos_pago-nuevo-activo": "on",
            "metodos_pago-nuevo-orden": "1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MetodoPago.objects.count(), 0)
        formulario = response.context["recurso"]["crear_formulario"]
        self.assertIn("numero_cuenta", formulario.errors)
        self.assertIn("titular", formulario.errors)

    def test_rechaza_nombre_duplicado(self):
        MetodoPago.objects.create(
            nombre="Daviplata",
            tipo="DAVIPLATA",
            banco="Daviplata",
            numero_cuenta="3009998877",
            titular="Oro del Sol",
            instrucciones="Paga por Daviplata",
        )
        response = self.client.post(self.url, {
            "recurso": "metodos_pago",
            "accion": "create",
            "metodos_pago-nuevo-nombre": "Daviplata",
            "metodos_pago-nuevo-tipo": "DAVIPLATA",
            "metodos_pago-nuevo-numero_cuenta": "3009998877",
            "metodos_pago-nuevo-titular": "Oro del Sol",
            "metodos_pago-nuevo-instrucciones": "Otra descripción",
            "metodos_pago-nuevo-activo": "on",
            "metodos_pago-nuevo-orden": "1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MetodoPago.objects.count(), 1)
        formulario = response.context["recurso"]["crear_formulario"]
        self.assertIn("nombre", formulario.errors)

    def test_edicion_metodo_pago(self):
        metodo = MetodoPago.objects.create(
            nombre="Bancolombia Ahorros",
            tipo="TRANSFERENCIA",
            banco="Bancolombia",
            numero_cuenta="111-222-333",
            titular="Oro del Sol",
            instrucciones="Instrucción previa",
            activo=True,
        )
        response = self.client.post(self.url, {
            "recurso": "metodos_pago",
            "accion": "edit",
            "registro": str(metodo.pk),
            f"metodos_pago-{metodo.pk}-nombre": "Bancolombia Ahorros",
            f"metodos_pago-{metodo.pk}-tipo": "TRANSFERENCIA",
            f"metodos_pago-{metodo.pk}-banco": "Bancolombia",
            f"metodos_pago-{metodo.pk}-tipo_cuenta": "AHORROS",
            f"metodos_pago-{metodo.pk}-numero_cuenta": "111-222-333",
            f"metodos_pago-{metodo.pk}-titular": "Oro del Sol S.A.S.",
            f"metodos_pago-{metodo.pk}-documento_titular": "900.123.456-7",
            f"metodos_pago-{metodo.pk}-instrucciones": "Nueva instrucción actualizada con soporte de WhatsApp",
            f"metodos_pago-{metodo.pk}-orden": "0",
            # Sin activo -> se desmarca
        })
        self.assertRedirects(response, f"{self.url}#registros")
        metodo.refresh_from_db()
        self.assertEqual(metodo.titular, "Oro del Sol S.A.S.")
        self.assertEqual(metodo.instrucciones, "Nueva instrucción actualizada con soporte de WhatsApp")
        self.assertFalse(metodo.activo)

    def test_accion_masiva_activa_y_desactiva_metodos(self):
        metodo = MetodoPago.objects.create(
            nombre="Efectivo Contraentrega",
            tipo="EFECTIVO",
            instrucciones="Pago en efectivo al recibir",
            activo=True,
        )
        response = self.client.post(self.url, {
            "recurso": "metodos_pago",
            "accion": "bulk",
            "estado": "0",
            "registros": [str(metodo.pk)],
        })
        self.assertRedirects(response, f"{self.url}#registros")
        metodo.refresh_from_db()
        self.assertFalse(metodo.activo)

        self.client.post(self.url, {
            "recurso": "metodos_pago",
            "accion": "bulk",
            "estado": "1",
            "registros": [str(metodo.pk)],
        })
        metodo.refresh_from_db()
        self.assertTrue(metodo.activo)

    def test_rutas_legadas_metodos_pago_redirigen_a_panel(self):
        response_list = self.client.get(reverse("configuracion:metodo_pago_list"))
        self.assertEqual(response_list.status_code, 302)
        self.assertEqual(response_list["Location"], self.url)

        response_create = self.client.get(reverse("configuracion:metodo_pago_create"))
        self.assertEqual(response_create.status_code, 302)
        self.assertEqual(response_create["Location"], self.url)


class PoliticaComercialCFG08Tests(TestCase):
    """Pruebas de la historia JODS-197: CFG-08 — Políticas comerciales."""

    def setUp(self):
        self.admin_user = Usuario.objects.create_superuser(
            username="admin_politicas",
            password="password123",
            email="admin-politicas@example.com",
            first_name="Admin",
            last_name="Politicas",
            tipo_documento="CC",
            documento="987654323",
            fecha_nacimiento="1990-01-01",
            telefono="3001234569",
        )
        self.cliente_user = Usuario.objects.create_user(
            username="cliente_politica",
            password="password123",
            email="cliente-pol@example.com",
            first_name="Cliente",
            last_name="B2C",
            tipo_documento="CC",
            documento="1122334456",
            fecha_nacimiento="1995-05-05",
            telefono="3119876544",
            rol="CLIENTE",
        )
        self.mayorista_user = Usuario.objects.create_user(
            username="mayorista_politica",
            password="password123",
            email="mayorista-pol@example.com",
            first_name="Mayorista",
            last_name="B2B",
            tipo_documento="CC",
            documento="1122334457",
            fecha_nacimiento="1988-08-08",
            telefono="3119876545",
            rol="MAYORISTA",
        )
        self.staff_sin_permiso = Usuario.objects.create_user(
            username="staff_sin_permiso_pol",
            password="password123",
            email="staff-pol@example.com",
            first_name="Staff",
            last_name="SinPermiso",
            tipo_documento="CC",
            documento="9988776656",
            fecha_nacimiento="1992-02-02",
            telefono="3009876544",
            is_staff=True,
        )
        self.client.force_login(self.admin_user)
        self.url = reverse(
            "core:admin_section",
            kwargs={"seccion": "politicas_comerciales"},
        )

    def test_admin_puede_acceder_al_panel_politicas_comerciales(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_custom/section.html")
        self.assertContains(response, "Políticas comerciales")

    def test_cliente_no_staff_es_redirigido_al_login(self):
        self.client.force_login(self.cliente_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_staff_sin_permiso_de_modelo_es_denegado(self):
        self.client.force_login(self.staff_sin_permiso)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_edicion_exitosa_politicas_comerciales_singleton(self):
        politica = PoliticaComercial.get_solo()
        response = self.client.post(self.url, {
            "recurso": "politicas_comerciales",
            "accion": "edit",
            "registro": str(politica.pk),
            f"politicas_comerciales-{politica.pk}-monto_minimo_compra_b2c": "50000.00",
            f"politicas_comerciales-{politica.pk}-monto_minimo_compra_b2b": "200000.00",
            f"politicas_comerciales-{politica.pk}-monto_minimo_envio_gratis": "150000.00",
            f"politicas_comerciales-{politica.pk}-tiempo_reserva_carrito_minutos": "45",
            f"politicas_comerciales-{politica.pk}-vigencia_cupones_dias": "15",
        })
        self.assertRedirects(response, f"{self.url}#registros")
        self.assertEqual(PoliticaComercial.objects.count(), 1)
        politica.refresh_from_db()
        self.assertEqual(politica.monto_minimo_compra_b2c, Decimal("50000.00"))
        self.assertEqual(politica.monto_minimo_compra_b2b, Decimal("200000.00"))
        self.assertEqual(politica.monto_minimo_envio_gratis, Decimal("150000.00"))
        self.assertEqual(politica.tiempo_reserva_carrito_minutos, 45)
        self.assertEqual(politica.vigencia_cupones_dias, 15)
        self.assertEqual(politica.actualizado_por, self.admin_user)

    def test_rechaza_montos_negativos(self):
        politica = PoliticaComercial.get_solo()
        response = self.client.post(self.url, {
            "recurso": "politicas_comerciales",
            "accion": "edit",
            "registro": str(politica.pk),
            f"politicas_comerciales-{politica.pk}-monto_minimo_compra_b2c": "-500.00",
            f"politicas_comerciales-{politica.pk}-monto_minimo_compra_b2b": "-1000.00",
            f"politicas_comerciales-{politica.pk}-monto_minimo_envio_gratis": "-10.00",
            f"politicas_comerciales-{politica.pk}-tiempo_reserva_carrito_minutos": "30",
            f"politicas_comerciales-{politica.pk}-vigencia_cupones_dias": "30",
        })
        self.assertEqual(response.status_code, 200)
        formulario = response.context["recurso"]["filas"][0]["formulario"]
        self.assertIn("monto_minimo_compra_b2c", formulario.errors)
        self.assertIn("monto_minimo_compra_b2b", formulario.errors)
        self.assertIn("monto_minimo_envio_gratis", formulario.errors)

    def test_rechaza_tiempos_invalidos(self):
        politica = PoliticaComercial.get_solo()
        response = self.client.post(self.url, {
            "recurso": "politicas_comerciales",
            "accion": "edit",
            "registro": str(politica.pk),
            f"politicas_comerciales-{politica.pk}-monto_minimo_compra_b2c": "0.00",
            f"politicas_comerciales-{politica.pk}-monto_minimo_compra_b2b": "0.00",
            f"politicas_comerciales-{politica.pk}-monto_minimo_envio_gratis": "0.00",
            f"politicas_comerciales-{politica.pk}-tiempo_reserva_carrito_minutos": "0",
            f"politicas_comerciales-{politica.pk}-vigencia_cupones_dias": "0",
        })
        self.assertEqual(response.status_code, 200)
        formulario = response.context["recurso"]["filas"][0]["formulario"]
        self.assertIn("tiempo_reserva_carrito_minutos", formulario.errors)
        self.assertIn("vigencia_cupones_dias", formulario.errors)

    def test_metodo_centralizado_validar_monto_minimo_b2b_y_b2c(self):
        politica = PoliticaComercial.get_solo()
        politica.monto_minimo_compra_b2c = Decimal("50000.00")
        politica.monto_minimo_compra_b2b = Decimal("200000.00")
        politica.save()

        # Validación cliente regular (B2C)
        valido_b2c, requerido_b2c = politica.validar_monto_minimo(self.cliente_user, Decimal("30000.00"))
        self.assertFalse(valido_b2c)
        self.assertEqual(requerido_b2c, Decimal("50000.00"))

        valido_b2c_ok, _ = politica.validar_monto_minimo(self.cliente_user, Decimal("50000.00"))
        self.assertTrue(valido_b2c_ok)

        # Validación mayorista (B2B)
        valido_b2b, requerido_b2b = politica.validar_monto_minimo(self.mayorista_user, Decimal("150000.00"))
        self.assertFalse(valido_b2b)
        self.assertEqual(requerido_b2b, Decimal("200000.00"))

        valido_b2b_ok, _ = politica.validar_monto_minimo(self.mayorista_user, Decimal("250000.00"))
        self.assertTrue(valido_b2b_ok)

    def test_metodo_centralizado_aplica_envio_gratis(self):
        politica = PoliticaComercial.get_solo()
        politica.monto_minimo_envio_gratis = Decimal("150000.00")
        politica.save()

        self.assertFalse(politica.aplica_envio_gratis(Decimal("100000.00")))
        self.assertTrue(politica.aplica_envio_gratis(Decimal("150000.00")))
        self.assertTrue(politica.aplica_envio_gratis(Decimal("180000.00")))

        # Con monto 0 queda desactivado
        politica.monto_minimo_envio_gratis = Decimal("0.00")
        politica.save()
        self.assertFalse(politica.aplica_envio_gratis(Decimal("500000.00")))

    def test_ruta_legada_politicas_comerciales_redirige_a_panel(self):
        response = self.client.get(reverse("configuracion:politica_comercial_detail"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], self.url)


class PlantillaDocumentoCFG07Tests(TestCase):
    """Pruebas de aceptación para CFG-07 (Plantillas de certificados, garantías y facturas)."""

    def setUp(self):
        self.admin_user = Usuario.objects.create_superuser(
            username="admin_docs",
            password="password123",
            email="admin-docs@example.com",
            first_name="Admin",
            last_name="Documentos",
            tipo_documento="CC",
            documento="987654324",
            fecha_nacimiento="1990-01-01",
            telefono="3001234570",
        )
        self.cliente_user = Usuario.objects.create_user(
            username="cliente_docs",
            password="password123",
            email="cliente-docs@example.com",
            first_name="Cliente",
            last_name="Docs",
            tipo_documento="CC",
            documento="1122334458",
            fecha_nacimiento="1995-05-05",
            telefono="3119876546",
            rol="CLIENTE",
        )
        self.staff_sin_permiso = Usuario.objects.create_user(
            username="staff_sin_permiso_docs",
            password="password123",
            email="staff-docs@example.com",
            first_name="Staff",
            last_name="SinPermisoDocs",
            tipo_documento="CC",
            documento="9988776657",
            fecha_nacimiento="1992-02-02",
            telefono="3009876545",
            is_staff=True,
        )
        self.client.force_login(self.admin_user)
        self.url = reverse(
            "core:admin_section",
            kwargs={"seccion": "plantillas_documentos"},
        )

    def test_admin_puede_acceder_al_panel_plantillas_documentos(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin_custom/section.html")
        self.assertContains(response, "Certificados y documentos")

    def test_cliente_no_staff_es_redirigido_al_login(self):
        self.client.force_login(self.cliente_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_staff_sin_permiso_de_modelo_es_denegado(self):
        self.client.force_login(self.staff_sin_permiso)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_creacion_exitosa_de_plantilla_pdf(self):
        archivo_pdf = SimpleUploadedFile(
            "certificado_pureza_18k.pdf",
            b"%PDF-1.4 simulacion de certificado de autenticidad en oro 18k",
            content_type="application/pdf",
        )
        response = self.client.post(self.url, {
            "recurso": "plantillas_documentos",
            "accion": "create",
            "plantillas_documentos-nuevo-nombre": "Certificado Pureza Oro 18K",
            "plantillas_documentos-nuevo-tipo": "CERTIFICADO",
            "plantillas_documentos-nuevo-archivo": archivo_pdf,
            "plantillas_documentos-nuevo-activa": "on",
            "plantillas_documentos-nuevo-descripcion": "Versión inicial del certificado oficial de pureza",
        })
        self.assertRedirects(response, f"{self.url}#registros")
        self.assertEqual(PlantillaDocumento.objects.count(), 1)

        plantilla = PlantillaDocumento.objects.first()
        self.assertEqual(plantilla.nombre, "Certificado Pureza Oro 18K")
        self.assertEqual(plantilla.tipo, "CERTIFICADO")
        self.assertEqual(plantilla.version, 1)
        self.assertTrue(plantilla.activa)
        self.assertEqual(plantilla.subido_por, self.admin_user)
        self.assertTrue(plantilla.archivo.name.endswith(".pdf"))

    def test_creacion_exitosa_de_plantilla_docx(self):
        archivo_docx = SimpleUploadedFile(
            "garantia_joyeria.docx",
            b"PK simulacion de contenido docx de garantia",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        response = self.client.post(self.url, {
            "recurso": "plantillas_documentos",
            "accion": "create",
            "plantillas_documentos-nuevo-nombre": "Póliza de Garantía Extendida",
            "plantillas_documentos-nuevo-tipo": "GARANTIA",
            "plantillas_documentos-nuevo-archivo": archivo_docx,
            "plantillas_documentos-nuevo-activa": "on",
            "plantillas_documentos-nuevo-descripcion": "Formato editable docx para garantías",
        })
        self.assertRedirects(response, f"{self.url}#registros")
        self.assertEqual(PlantillaDocumento.objects.count(), 1)
        plantilla = PlantillaDocumento.objects.first()
        self.assertEqual(plantilla.tipo, "GARANTIA")
        self.assertTrue(plantilla.archivo.name.endswith(".docx"))

    def test_versionado_conserva_anterior_e_incrementa_version_y_vigencia(self):
        # 1. Crear versión 1
        archivo_v1 = SimpleUploadedFile("cert_v1.pdf", b"%PDF-1.4 version 1", content_type="application/pdf")
        self.client.post(self.url, {
            "recurso": "plantillas_documentos",
            "accion": "create",
            "plantillas_documentos-nuevo-nombre": "Certificado Pureza",
            "plantillas_documentos-nuevo-tipo": "CERTIFICADO",
            "plantillas_documentos-nuevo-archivo": archivo_v1,
            "plantillas_documentos-nuevo-activa": "on",
            "plantillas_documentos-nuevo-descripcion": "Primera edición 2026",
        })
        self.assertEqual(PlantillaDocumento.objects.count(), 1)
        v1 = PlantillaDocumento.objects.first()
        self.assertEqual(v1.version, 1)
        self.assertTrue(v1.activa)
        archivo_v1_nombre = v1.archivo.name

        # 2. Subir versión 2 (marcada como activa)
        archivo_v2 = SimpleUploadedFile("cert_v2.pdf", b"%PDF-1.4 version 2 mejorada", content_type="application/pdf")
        self.client.post(self.url, {
            "recurso": "plantillas_documentos",
            "accion": "create",
            "plantillas_documentos-nuevo-nombre": "Certificado Pureza Actualizado",
            "plantillas_documentos-nuevo-tipo": "CERTIFICADO",
            "plantillas_documentos-nuevo-archivo": archivo_v2,
            "plantillas_documentos-nuevo-activa": "on",
            "plantillas_documentos-nuevo-descripcion": "Segunda edición con sello holográfico",
        })

        # Criterio: Se conservan versiones anteriores (no se sobreescribe ni se borra)
        self.assertEqual(PlantillaDocumento.objects.count(), 2)

        v1.refresh_from_db()
        v2 = PlantillaDocumento.objects.get(version=2)

        # La versión 1 se conserva histórica e inactiva
        self.assertFalse(v1.activa)
        self.assertEqual(v1.version, 1)
        self.assertEqual(v1.archivo.name, archivo_v1_nombre)

        # La versión 2 queda como vigente
        self.assertTrue(v2.activa)
        self.assertEqual(v2.version, 2)
        self.assertEqual(v2.subido_por, self.admin_user)
        self.assertNotEqual(v1.archivo.name, v2.archivo.name)

    def test_rechaza_formato_de_archivo_no_permitido(self):
        archivo_invalido = SimpleUploadedFile(
            "script_malicioso.exe",
            b"MZ peligro",
            content_type="application/x-msdownload",
        )
        response = self.client.post(self.url, {
            "recurso": "plantillas_documentos",
            "accion": "create",
            "plantillas_documentos-nuevo-nombre": "Documento Inválido",
            "plantillas_documentos-nuevo-tipo": "FACTURA",
            "plantillas_documentos-nuevo-archivo": archivo_invalido,
            "plantillas_documentos-nuevo-activa": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlantillaDocumento.objects.count(), 0)
        formulario = response.context["recurso"]["crear_formulario"]
        self.assertIn("archivo", formulario.errors)
        self.assertTrue(any("Formato de archivo no permitido" in e for e in formulario.errors["archivo"]))

    def test_rechaza_archivo_que_supera_tamano_maximo_10mb(self):
        # Archivo simulado de 11 MB
        tamano_11mb = 11 * 1024 * 1024
        archivo_pesado = SimpleUploadedFile(
            "archivo_gigante.pdf",
            b"0" * tamano_11mb,
            content_type="application/pdf",
        )
        response = self.client.post(self.url, {
            "recurso": "plantillas_documentos",
            "accion": "create",
            "plantillas_documentos-nuevo-nombre": "Plantilla Pesada",
            "plantillas_documentos-nuevo-tipo": "FACTURA",
            "plantillas_documentos-nuevo-archivo": archivo_pesado,
            "plantillas_documentos-nuevo-activa": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlantillaDocumento.objects.count(), 0)
        formulario = response.context["recurso"]["crear_formulario"]
        self.assertIn("archivo", formulario.errors)
        self.assertTrue(any("excede el tamaño máximo permitido de 10 MB" in e for e in formulario.errors["archivo"]))

    def test_rechaza_campos_obligatorios_vacios(self):
        # Sin nombre ni archivo
        response = self.client.post(self.url, {
            "recurso": "plantillas_documentos",
            "accion": "create",
            "plantillas_documentos-nuevo-nombre": "",
            "plantillas_documentos-nuevo-tipo": "CERTIFICADO",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PlantillaDocumento.objects.count(), 0)
        formulario = response.context["recurso"]["crear_formulario"]
        self.assertIn("nombre", formulario.errors)
        self.assertIn("archivo", formulario.errors)

    def test_edicion_metadatos_plantilla(self):
        archivo_pdf = SimpleUploadedFile("garantia.pdf", b"%PDF-1.4 garantia", content_type="application/pdf")
        plantilla = PlantillaDocumento.objects.create(
            nombre="Garantía Estándar",
            tipo="GARANTIA",
            archivo=archivo_pdf,
            version=1,
            activa=True,
            subido_por=self.admin_user,
        )

        response = self.client.post(self.url, {
            "recurso": "plantillas_documentos",
            "accion": "edit",
            "registro": str(plantilla.pk),
            f"plantillas_documentos-{plantilla.pk}-nombre": "Garantía Estándar Modificada",
            f"plantillas_documentos-{plantilla.pk}-tipo": "GARANTIA",
            f"plantillas_documentos-{plantilla.pk}-descripcion": "Ajuste de descripción sin cambiar archivo",
        })
        self.assertRedirects(response, f"{self.url}#registros")
        plantilla.refresh_from_db()
        self.assertEqual(plantilla.nombre, "Garantía Estándar Modificada")
        self.assertEqual(plantilla.descripcion, "Ajuste de descripción sin cambiar archivo")
        self.assertEqual(plantilla.actualizado_por, self.admin_user)

    def test_asociacion_automatica_de_plantilla_vigente(self):
        # 1. Crear versión 1 inactiva y versión 2 activa de CERTIFICADO
        pdf1 = SimpleUploadedFile("cert1.pdf", b"%PDF v1", content_type="application/pdf")
        p1 = PlantillaDocumento.objects.create(
            nombre="Cert v1", tipo="CERTIFICADO", archivo=pdf1, version=1, activa=False, subido_por=self.admin_user
        )
        pdf2 = SimpleUploadedFile("cert2.pdf", b"%PDF v2", content_type="application/pdf")
        p2 = PlantillaDocumento.objects.create(
            nombre="Cert v2", tipo="CERTIFICADO", archivo=pdf2, version=2, activa=True, subido_por=self.admin_user
        )

        # 2. Crear GARANTIA activa
        pdf_gar = SimpleUploadedFile("gar.pdf", b"%PDF gar", content_type="application/pdf")
        p_gar = PlantillaDocumento.objects.create(
            nombre="Garantía Vigente", tipo="GARANTIA", archivo=pdf_gar, version=1, activa=True, subido_por=self.admin_user
        )

        # Verificación mediante método de dominio
        vigente_cert = PlantillaDocumento.obtener_vigente("CERTIFICADO")
        self.assertEqual(vigente_cert, p2)

        # Verificación mediante servicio desacoplado
        vigente_gar = obtener_plantilla_vigente("GARANTIA")
        self.assertEqual(vigente_gar, p_gar)

        # Tipo sin plantilla configurada
        vigente_factura = obtener_plantilla_vigente("FACTURA")
        self.assertIsNone(vigente_factura)

    def test_accion_masiva_desactiva_plantillas(self):
        pdf1 = SimpleUploadedFile("doc1.pdf", b"%PDF 1", content_type="application/pdf")
        pdf2 = SimpleUploadedFile("doc2.pdf", b"%PDF 2", content_type="application/pdf")
        p1 = PlantillaDocumento.objects.create(
            nombre="Doc 1", tipo="CERTIFICADO", archivo=pdf1, version=1, activa=True, subido_por=self.admin_user
        )
        p2 = PlantillaDocumento.objects.create(
            nombre="Doc 2", tipo="GARANTIA", archivo=pdf2, version=1, activa=True, subido_por=self.admin_user
        )

        response = self.client.post(self.url, {
            "recurso": "plantillas_documentos",
            "accion": "bulk",
            "estado": "0",
            "registros": [str(p1.pk), str(p2.pk)],
        })
        self.assertRedirects(response, f"{self.url}#registros")
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertFalse(p1.activa)
        self.assertFalse(p2.activa)

    def test_rutas_legadas_plantillas_redirigen_a_panel(self):
        res1 = self.client.get(reverse("configuracion:plantilla_documento_list"))
        self.assertEqual(res1.status_code, 302)
        self.assertEqual(res1["Location"], self.url)

        res2 = self.client.get(reverse("configuracion:plantilla_documento_create"))
        self.assertEqual(res2.status_code, 302)
        self.assertEqual(res2["Location"], self.url)


        
        
