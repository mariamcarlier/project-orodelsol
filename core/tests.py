from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from configuracion.models import Idioma, Impuesto, Moneda, ParametroGeneral

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

	def test_cada_recurso_usa_la_plantilla_compartida(self):
		for recurso in RECURSOS:
			with self.subTest(recurso=recurso["key"]):
				response = self.client.get(
					reverse(
						"core:admin_section",
						kwargs={"seccion": recurso["key"]},
					)
				)

				self.assertEqual(response.status_code, 200)
				self.assertTemplateUsed(response, "admin_custom/section.html")
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

	def test_usuario_con_rol_admin_pero_sin_is_staff_no_accede_al_panel(self):
		usuario = get_user_model().objects.create_user(
			username="admin_sin_staff",
			password="password123",
			rol="ADMIN",
			first_name="Admin",
			last_name="Sin acceso",
			tipo_documento="CC",
			documento="987654321",
			fecha_nacimiento=date(1990, 1, 1),
		)
		self.client.force_login(usuario)

		response = self.client.get(
			reverse("core:admin_section", kwargs={"seccion": "impuestos"})
		)

		self.assertEqual(response.status_code, 302)
		self.assertIn("/admin/login/", response.url)

	def test_staff_sin_permiso_de_modelo_no_accede_a_la_seccion(self):
		usuario = get_user_model().objects.create_user(
			username="staff_sin_permiso",
			password="password123",
			is_staff=True,
			first_name="Staff",
			last_name="Sin permiso",
			tipo_documento="CC",
			documento="876543210",
			fecha_nacimiento=date(1990, 1, 1),
		)
		self.client.force_login(usuario)

		response = self.client.get(
			reverse("core:admin_section", kwargs={"seccion": "impuestos"})
		)

		self.assertEqual(response.status_code, 403)

	def test_staff_con_permiso_de_modelo_puede_ver_la_seccion(self):
		usuario = get_user_model().objects.create_user(
			username="staff_con_permiso",
			password="password123",
			is_staff=True,
			first_name="Staff",
			last_name="Con permiso",
			tipo_documento="CC",
			documento="765432109",
			fecha_nacimiento=date(1990, 1, 1),
		)
		permiso_ver_impuesto = Permission.objects.get(
			content_type__app_label="configuracion",
			codename="view_impuesto",
		)
		usuario.user_permissions.add(permiso_ver_impuesto)
		self.client.force_login(usuario)

		response = self.client.get(
			reverse("core:admin_section", kwargs={"seccion": "impuestos"})
		)

		self.assertEqual(response.status_code, 200)

	def test_crear_impuesto_desde_el_panel_respeta_nombre_unico(self):
		url = reverse("core:admin_section", kwargs={"seccion": "impuestos"})
		impuesto = Impuesto.objects.create(nombre="IVA", tasa="19.00")

		response = self.client.post(url, {
			"recurso": "impuestos",
			"accion": "create",
			"impuestos-nuevo-nombre": "IVA",
			"impuestos-nuevo-tasa": "16.00",
			"impuestos-nuevo-vigente": "on",
		})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(Impuesto.objects.count(), 1)
		impuesto.refresh_from_db()
		self.assertEqual(impuesto.tasa, Decimal("19.00"))

	def test_crear_impuesto_desde_el_panel(self):
		url = reverse("core:admin_section", kwargs={"seccion": "impuestos"})

		response = self.client.post(url, {
			"recurso": "impuestos",
			"accion": "create",
			"impuestos-nuevo-nombre": "IVA",
			"impuestos-nuevo-tasa": "19.00",
			"impuestos-nuevo-vigente": "on",
		})

		self.assertEqual(response.status_code, 302)
		self.assertEqual(Impuesto.objects.get().nombre, "IVA")

	def test_listado_del_panel_muestra_los_registros(self):
		Impuesto.objects.create(nombre="IVA", tasa="19.00")
		url = reverse("core:admin_section", kwargs={"seccion": "impuestos"})

		response = self.client.get(url)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "IVA")
		self.assertContains(response, "19.00")

	def test_crear_moneda_principal_desmarca_la_anterior(self):
		Moneda.objects.create(
			codigo_iso="COP",
			nombre="Peso colombiano",
			simbolo="$",
			es_principal=True,
		)
		url = reverse("core:admin_section", kwargs={"seccion": "monedas"})

		response = self.client.post(url, {
			"recurso": "monedas",
			"accion": "create",
			"monedas-nuevo-codigo_iso": "USD",
			"monedas-nuevo-nombre": "Dólar estadounidense",
			"monedas-nuevo-simbolo": "$",
			"monedas-nuevo-tasa_cambio": "1.0000",
			"monedas-nuevo-es_principal": "on",
			"monedas-nuevo-activa": "on",
		})

		self.assertEqual(response.status_code, 302)
		self.assertFalse(Moneda.objects.get(codigo_iso="COP").es_principal)
		self.assertTrue(Moneda.objects.get(codigo_iso="USD").es_principal)

	def test_rechazar_moneda_con_codigo_iso_duplicado(self):
		Moneda.objects.create(
			codigo_iso="COP",
			nombre="Peso colombiano",
			simbolo="$",
		)
		url = reverse("core:admin_section", kwargs={"seccion": "monedas"})

		response = self.client.post(url, {
			"recurso": "monedas",
			"accion": "create",
			"monedas-nuevo-codigo_iso": "COP",
			"monedas-nuevo-nombre": "Peso duplicado",
			"monedas-nuevo-simbolo": "$",
			"monedas-nuevo-tasa_cambio": "1.0000",
			"monedas-nuevo-activa": "on",
		})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(Moneda.objects.count(), 1)

	def test_crear_idioma_principal_desmarca_el_anterior(self):
		Idioma.objects.create(codigo="es", nombre="Español", es_principal=True)
		url = reverse("core:admin_section", kwargs={"seccion": "idiomas"})

		response = self.client.post(url, {
			"recurso": "idiomas",
			"accion": "create",
			"idiomas-nuevo-codigo": "en",
			"idiomas-nuevo-nombre": "English",
			"idiomas-nuevo-es_principal": "on",
			"idiomas-nuevo-activo": "on",
		})

		self.assertEqual(response.status_code, 302)
		self.assertFalse(Idioma.objects.get(codigo="es").es_principal)
		self.assertTrue(Idioma.objects.get(codigo="en").es_principal)

	def test_rechazar_idioma_con_codigo_duplicado(self):
		Idioma.objects.create(codigo="es", nombre="Español")
		url = reverse("core:admin_section", kwargs={"seccion": "idiomas"})

		response = self.client.post(url, {
			"recurso": "idiomas",
			"accion": "create",
			"idiomas-nuevo-codigo": "es",
			"idiomas-nuevo-nombre": "Español duplicado",
		})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(Idioma.objects.count(), 1)

	def test_editar_parametros_registra_usuario_y_fecha_de_actualizacion(self):
		parametros = ParametroGeneral.get_solo()
		url = reverse("core:admin_section", kwargs={"seccion": "parametros"})

		response = self.client.post(url, {
			"recurso": "parametros",
			"accion": "edit",
			"registro": parametros.pk,
			f"parametros-{parametros.pk}-nombre_tienda": "Oro del Sol actualizado",
			f"parametros-{parametros.pk}-lema": "Joyería fina",
			f"parametros-{parametros.pk}-nit": "901.999.888-1",
			f"parametros-{parametros.pk}-correo_contacto": "info@orodelsol.com",
			f"parametros-{parametros.pk}-telefono_contacto": "3001234567",
			f"parametros-{parametros.pk}-direccion": "Carrera 15",
			f"parametros-{parametros.pk}-ciudad": "Bogotá",
			f"parametros-{parametros.pk}-horario_atencion": "Lunes a viernes",
		})

		self.assertEqual(response.status_code, 302)
		parametros.refresh_from_db()
		self.assertEqual(parametros.nombre_tienda, "Oro del Sol actualizado")
		self.assertEqual(parametros.actualizado_por.username, "administrador")
		self.assertIsNotNone(parametros.fecha_actualizacion)

	def test_editar_parametros_rechaza_nombre_obligatorio_vacio(self):
		parametros = ParametroGeneral.get_solo()
		nombre_original = parametros.nombre_tienda
		url = reverse("core:admin_section", kwargs={"seccion": "parametros"})

		response = self.client.post(url, {
			"recurso": "parametros",
			"accion": "edit",
			"registro": parametros.pk,
			f"parametros-{parametros.pk}-nombre_tienda": "",
			f"parametros-{parametros.pk}-lema": "",
			f"parametros-{parametros.pk}-nit": "901.999.888-1",
			f"parametros-{parametros.pk}-correo_contacto": "info@orodelsol.com",
			f"parametros-{parametros.pk}-telefono_contacto": "3001234567",
			f"parametros-{parametros.pk}-direccion": "Carrera 15",
			f"parametros-{parametros.pk}-ciudad": "Bogotá",
			f"parametros-{parametros.pk}-horario_atencion": "",
		})

		self.assertEqual(response.status_code, 200)
		parametros.refresh_from_db()
		self.assertEqual(parametros.nombre_tienda, nombre_original)
		self.assertTrue(response.context["recurso"]["filas"][0]["formulario"].errors)

	def test_parametros_generales_no_permiten_crear_un_segundo_registro(self):
		ParametroGeneral.get_solo()
		url = reverse("core:admin_section", kwargs={"seccion": "parametros"})

		response = self.client.get(url)

		self.assertEqual(response.status_code, 200)
		self.assertIsNone(response.context["recurso"]["crear_formulario"])
