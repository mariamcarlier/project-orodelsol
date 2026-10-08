from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

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

	def test_cada_recurso_tiene_pagina_y_plantilla_propia(self):
		for recurso in RECURSOS:
			with self.subTest(recurso=recurso["key"]):
				response = self.client.get(
					reverse(
						"core:admin_section",
						kwargs={"seccion": recurso["key"]},
					)
				)

				self.assertEqual(response.status_code, 200)
				self.assertTemplateUsed(
					response,
					f"admin_custom/sections/{recurso['key']}.html",
				)
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
