from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from configuracion.models import Impuesto

Usuario = get_user_model()


class ImpuestoCFG02Tests(TestCase):
    """
    Pruebas automatizadas para la historia de usuario JODS-191:
    CFG-02 — Configuración — Administrar impuestos.
    """

    def setUp(self):
        self.client = Client()
        self.list_url = reverse('configuracion:impuesto_list')
        self.create_url = reverse('configuracion:impuesto_create')

        # Usuario con rol ADMINISTRADOR
        self.admin_user = Usuario.objects.create_user(
            username='admin_test',
            password='password123',
            rol='ADMIN',
            first_name='Admin',
            last_name='User',
            tipo_documento='CC',
            documento='100100100',
            fecha_nacimiento='1990-01-01'
        )

        # Usuario con rol CLIENTE (no administrador)
        self.cliente_user = Usuario.objects.create_user(
            username='cliente_test',
            password='password123',
            rol='CLIENTE',
            first_name='Cliente',
            last_name='User',
            tipo_documento='CC',
            documento='200200200',
            fecha_nacimiento='1995-05-05'
        )

    # ── ESCENARIO 2: CONTROL DE ACCESO POR ROL ───────────────────────

    def test_acceso_anonimo_redirige_a_login_en_lista(self):
        """Usuario no autenticado debe ser redirigido a login al intentar ver la lista."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_acceso_anonimo_redirige_a_login_en_creacion(self):
        """Usuario no autenticado debe ser redirigido a login al intentar crear un impuesto."""
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_usuario_no_admin_recibe_403_en_lista(self):
        """Usuario autenticado pero sin rol ADMIN debe recibir HTTP 403 Forbidden."""
        self.client.login(username='cliente_test', password='password123')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 403)

    def test_usuario_no_admin_recibe_403_en_creacion(self):
        """Usuario autenticado sin rol ADMIN debe recibir HTTP 403 al intentar crear."""
        self.client.login(username='cliente_test', password='password123')
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 403)

        response_post = self.client.post(self.create_url, {
            'nombre': 'Intento Ilegal',
            'tasa': '10.00',
            'vigente': True
        })
        self.assertEqual(response_post.status_code, 403)

    # ── ESCENARIO 1: LISTADO Y CREACIÓN POR ADMINISTRADOR ─────────────

    def test_admin_puede_acceder_a_lista_impuestos(self):
        """Administrador puede acceder exitosamente al listado de impuestos."""
        self.client.login(username='admin_test', password='password123')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'configuracion/impuestos.html')

    def test_admin_puede_ver_formulario_nuevo_impuesto(self):
        """Administrador puede ver el formulario y se incluye correctamente el parcial _form_fields."""
        self.client.login(username='admin_test', password='password123')
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'configuracion/impuesto_form.html')
        self.assertTemplateUsed(response, 'configuracion/partials/_form_fields.html')

    def test_creacion_exitosa_de_impuesto_valido(self):
        """Administrador registra un nuevo impuesto con datos válidos y redirige a la lista."""
        self.client.login(username='admin_test', password='password123')
        datos = {
            'nombre': 'IVA 19%',
            'tasa': '19.00',
            'vigente': True
        }
        response = self.client.post(self.create_url, datos)
        # Redirección a la lista
        self.assertRedirects(response, self.list_url)

        # Verificación en la base de datos
        impuesto = Impuesto.objects.filter(nombre='IVA 19%').first()
        self.assertIsNotNone(impuesto)
        self.assertEqual(impuesto.tasa, Decimal('19.00'))
        self.assertTrue(impuesto.vigente)

    def test_rechazo_de_impuesto_con_nombre_duplicado(self):
        """No debe permitir registrar dos impuestos con el mismo nombre (unique=True)."""
        Impuesto.objects.create(nombre='IVA General', tasa=Decimal('19.00'), vigente=True)

        self.client.login(username='admin_test', password='password123')
        response = self.client.post(self.create_url, {
            'nombre': 'IVA General',
            'tasa': '16.00',
            'vigente': True
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(Impuesto.objects.filter(nombre='IVA General').count(), 1)

    def test_impuesto_aparece_en_listado(self):
        """Un impuesto creado aparece en la tabla del listado con su nombre y tasa."""
        Impuesto.objects.create(nombre='IVA Joyería 19%', tasa=Decimal('19.00'), vigente=True)

        self.client.login(username='admin_test', password='password123')
        response = self.client.get(self.list_url)
        self.assertContains(response, 'IVA Joyería 19%')
        self.assertContains(response, '19,00 %')
        self.assertContains(response, 'Activo')
