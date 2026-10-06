from django.test import TestCase

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
