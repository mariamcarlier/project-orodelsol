
"""Regresión: la plantilla del formulario de producto debe poder renderizarse.

`templates/core/productos/form.html` quedó con un `{% if %}` y un `<span>` de
ayuda duplicados (restos de una fusión), lo que producía un TemplateSyntaxError
y un error 500 al abrir «Nuevo producto», «Editar producto» o al reenviar el
formulario con errores. Ninguna prueba renderizaba esta plantilla.

Se usa un superusuario para que estas pruebas solo midan la plantilla y no
dependan de la política de permisos de las vistas. Los textos que provienen del
formulario o de la vista se leen de ellos (no se copian aquí), de modo que
reformular un mensaje no rompa estas pruebas; solo se fija el texto genérico de
ayuda, que pertenece a la propia plantilla.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .dashboard import ProductoForm
from .models import Coleccion, Producto

AYUDA_GENERICA = "Activa esta opción para mostrarla en el catálogo."


def _interruptores():
    """Campos que la plantilla debe pintar como interruptor (casilla simple)."""
    # `getattr`: algunos widgets (Textarea) no definen `input_type`; la plantilla
    # de Django lo resuelve como vacío en lugar de fallar.
    return [
        campo
        for campo in ProductoForm()
        if getattr(campo.field.widget, "input_type", None) == "checkbox"
        and not getattr(campo.field.widget, "allow_multiple_selected", False)
    ]


class FormularioProductoPlantillaTests(TestCase):
    def setUp(self):
        administrador = get_user_model().objects.create_superuser(
            username="administrador",
            password="clave-de-prueba",
            first_name="Admin",
            last_name="Prueba",
            tipo_documento="CC",
            documento="123456789",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
        )
        self.client.force_login(administrador)
        self.coleccion = Coleccion.objects.create(nombre="Alma Dorada")
        self.producto = Producto.objects.create(
            coleccion=self.coleccion,
            nombre="Anillo Aurora",
            precio=Decimal("1000000.00"),
            imagen_url="https://example.com/aurora.jpg",
        )

    def test_el_formulario_de_alta_se_muestra(self):
        respuesta = self.client.get(reverse("core:producto_crear"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, respuesta.context["titulo"])

    def test_el_formulario_de_edicion_se_muestra_con_los_datos_del_producto(self):
        respuesta = self.client.get(
            reverse("core:producto_editar", args=[self.producto.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.producto.nombre)

    def test_un_envio_con_errores_vuelve_a_mostrar_el_formulario(self):
        respuesta = self.client.post(
            reverse("core:producto_crear"),
            {"nombre": "", "coleccion": self.coleccion.pk, "precio": "0"},
        )

        self.assertEqual(respuesta.status_code, 200)
        formulario = respuesta.context["form"]
        self.assertIn("precio", formulario.errors)
        self.assertContains(respuesta, formulario.errors["precio"][0])
        self.assertFalse(Producto.objects.filter(nombre="").exists())

    def test_solo_los_campos_si_o_no_se_pintan_como_interruptor(self):
        # Las casillas múltiples (tallas, materiales) deben mostrarse como
        # campos normales; si la plantilla las tratara como interruptor, el
        # total de interruptores superaría al de casillas simples.
        esperados = _interruptores()
        self.assertGreaterEqual(len(esperados), 1)

        respuesta = self.client.get(reverse("core:producto_crear"))

        self.assertContains(
            respuesta, "producto-form__field--toggle", count=len(esperados)
        )

    def test_la_ayuda_de_cada_interruptor_aparece_una_sola_vez(self):
        interruptores = _interruptores()
        sin_ayuda_propia = [c for c in interruptores if not c.help_text]
        con_ayuda_propia = [c for c in interruptores if c.help_text]
        self.assertTrue(sin_ayuda_propia and con_ayuda_propia)

        respuesta = self.client.get(reverse("core:producto_crear"))

        # Sin ayuda propia: texto genérico, una vez por campo.
        self.assertContains(respuesta, AYUDA_GENERICA, count=len(sin_ayuda_propia))
        # Con ayuda propia: se muestra la suya, una vez, sin añadir la genérica.
        for campo in con_ayuda_propia:
            self.assertContains(respuesta, str(campo.help_text), count=1)
