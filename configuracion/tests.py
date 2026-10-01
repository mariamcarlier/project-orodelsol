from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from configuracion.models import Impuesto, Moneda, Idioma

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


class MonedaCFG03Tests(TestCase):
    """
    Pruebas automatizadas para la historia de usuario JODS-192:
    CFG-03 — Configuración — Configurar monedas.
    """

    def setUp(self):
        self.client = Client()
        self.list_url = reverse('configuracion:moneda_list')
        self.create_url = reverse('configuracion:moneda_create')

        # Usuario con rol ADMINISTRADOR
        self.admin_user = Usuario.objects.create_user(
            username='admin_moneda',
            password='password123',
            rol='ADMIN',
            first_name='Admin',
            last_name='Moneda',
            tipo_documento='CC',
            documento='300300300',
            fecha_nacimiento='1990-01-01'
        )

        # Usuario con rol CLIENTE
        self.cliente_user = Usuario.objects.create_user(
            username='cliente_moneda',
            password='password123',
            rol='CLIENTE',
            first_name='Cliente',
            last_name='Moneda',
            tipo_documento='CC',
            documento='400400400',
            fecha_nacimiento='1995-05-05'
        )

    # ── ESCENARIO 3: CONTROL DE ACCESO POR ROL ───────────────────────

    def test_acceso_anonimo_redirige_a_login_en_lista_monedas(self):
        """Usuario no autenticado debe ser redirigido a login al intentar ver monedas."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_acceso_anonimo_redirige_a_login_en_creacion_moneda(self):
        """Usuario no autenticado debe ser redirigido a login al intentar crear moneda."""
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_usuario_no_admin_recibe_403_en_lista_monedas(self):
        """Usuario autenticado sin rol ADMIN recibe HTTP 403 Forbidden."""
        self.client.login(username='cliente_moneda', password='password123')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 403)

    def test_usuario_no_admin_recibe_403_en_creacion_moneda(self):
        """Usuario autenticado sin rol ADMIN recibe HTTP 403 al crear moneda."""
        self.client.login(username='cliente_moneda', password='password123')
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 403)

        response_post = self.client.post(self.create_url, {
            'codigo_iso': 'USD',
            'nombre': 'Dólar',
            'simbolo': '$',
            'tasa_cambio': '1.0000',
            'es_principal': False,
            'activa': True
        })
        self.assertEqual(response_post.status_code, 403)

    # ── ESCENARIO 1: LISTADO Y REGISTRO DE MONEDA ─────────────────────

    def test_admin_puede_acceder_a_lista_monedas(self):
        """Administrador puede acceder exitosamente al listado de monedas."""
        self.client.login(username='admin_moneda', password='password123')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'configuracion/monedas.html')

    def test_admin_puede_ver_formulario_nueva_moneda(self):
        """Administrador puede ver el formulario y se incluye el parcial _form_fields."""
        self.client.login(username='admin_moneda', password='password123')
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'configuracion/moneda_form.html')
        self.assertTemplateUsed(response, 'configuracion/partials/_form_fields.html')

    def test_creacion_exitosa_de_moneda_valida(self):
        """Administrador registra una moneda válida y redirige a la lista."""
        self.client.login(username='admin_moneda', password='password123')
        datos = {
            'codigo_iso': 'COP',
            'nombre': 'Peso colombiano',
            'simbolo': '$',
            'tasa_cambio': '1.0000',
            'es_principal': True,
            'activa': True
        }
        response = self.client.post(self.create_url, datos)
        self.assertRedirects(response, self.list_url)

        moneda = Moneda.objects.filter(codigo_iso='COP').first()
        self.assertIsNotNone(moneda)
        self.assertEqual(moneda.nombre, 'Peso colombiano')
        self.assertTrue(moneda.es_principal)
        self.assertTrue(moneda.activa)

    def test_rechazo_de_moneda_con_codigo_iso_duplicado(self):
        """No permite registrar dos monedas con el mismo código ISO (unique=True)."""
        Moneda.objects.create(
            codigo_iso='COP', nombre='Peso colombiano', simbolo='$',
            tasa_cambio=Decimal('1.0000'), es_principal=True, activa=True
        )

        self.client.login(username='admin_moneda', password='password123')
        response = self.client.post(self.create_url, {
            'codigo_iso': 'COP',
            'nombre': 'Otro Peso',
            'simbolo': '$',
            'tasa_cambio': '1.0000',
            'es_principal': False,
            'activa': True
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(Moneda.objects.filter(codigo_iso='COP').count(), 1)

    # ── ESCENARIO 2: REGLA DE NEGOCIO — MONEDA PRINCIPAL ÚNICA ────────

    def test_regla_moneda_principal_unica_al_crear(self):
        """
        Al registrar una nueva moneda con es_principal=True, la moneda
        principal anterior se desmarca automáticamente a es_principal=False.
        """
        cop = Moneda.objects.create(
            codigo_iso='COP', nombre='Peso colombiano', simbolo='$',
            tasa_cambio=Decimal('1.0000'), es_principal=True, activa=True
        )
        self.assertTrue(cop.es_principal)

        self.client.login(username='admin_moneda', password='password123')
        response = self.client.post(self.create_url, {
            'codigo_iso': 'USD',
            'nombre': 'Dólar estadounidense',
            'simbolo': 'US$',
            'tasa_cambio': '1.0000',
            'es_principal': True,
            'activa': True
        })
        self.assertRedirects(response, self.list_url)

        # Refrescar desde BD
        cop.refresh_from_db()
        usd = Moneda.objects.get(codigo_iso='USD')

        # COP ya no es principal, USD ahora es principal
        self.assertFalse(cop.es_principal)
        self.assertTrue(usd.es_principal)
        self.assertEqual(Moneda.objects.filter(es_principal=True).count(), 1)

    def test_moneda_aparece_en_listado(self):
        """Moneda configurada se renderiza en la tabla con sus datos y badge."""
        Moneda.objects.create(
            codigo_iso='COP', nombre='Peso colombiano', simbolo='$',
            tasa_cambio=Decimal('1.0000'), es_principal=True, activa=True
        )

        self.client.login(username='admin_moneda', password='password123')
        response = self.client.get(self.list_url)
        self.assertContains(response, 'COP')
        self.assertContains(response, 'Peso colombiano')
        self.assertContains(response, 'Principal')
        self.assertContains(response, 'Activa')


class IdiomaCFG04Tests(TestCase):
    """
    Pruebas automatizadas para la historia de usuario JODS-193:
    CFG-04 — Configuración — Configurar idiomas.
    """

    def setUp(self):
        self.client = Client()
        self.list_url = reverse('configuracion:idioma_list')
        self.create_url = reverse('configuracion:idioma_create')

        # Usuario con rol ADMINISTRADOR
        self.admin_user = Usuario.objects.create_user(
            username='admin_idioma',
            password='password123',
            rol='ADMIN',
            first_name='Admin',
            last_name='Idioma',
            tipo_documento='CC',
            documento='500500500',
            fecha_nacimiento='1990-01-01'
        )

        # Usuario con rol CLIENTE
        self.cliente_user = Usuario.objects.create_user(
            username='cliente_idioma',
            password='password123',
            rol='CLIENTE',
            first_name='Cliente',
            last_name='Idioma',
            tipo_documento='CC',
            documento='600600600',
            fecha_nacimiento='1995-05-05'
        )

    # ── ESCENARIO 3: CONTROL DE ACCESO POR ROL ───────────────────────

    def test_acceso_anonimo_redirige_a_login_en_lista_idiomas(self):
        """Usuario no autenticado debe ser redirigido a login al intentar ver idiomas."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_acceso_anonimo_redirige_a_login_en_creacion_idioma(self):
        """Usuario no autenticado debe ser redirigido a login al intentar crear idioma."""
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_usuario_no_admin_recibe_403_en_lista_idiomas(self):
        """Usuario autenticado sin rol ADMIN recibe HTTP 403 Forbidden."""
        self.client.login(username='cliente_idioma', password='password123')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 403)

    def test_usuario_no_admin_recibe_403_en_creacion_idioma(self):
        """Usuario autenticado sin rol ADMIN recibe HTTP 403 al crear idioma."""
        self.client.login(username='cliente_idioma', password='password123')
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 403)

        response_post = self.client.post(self.create_url, {
            'codigo': 'en',
            'nombre': 'English',
            'es_principal': False,
            'activo': True
        })
        self.assertEqual(response_post.status_code, 403)

    # ── ESCENARIO 1: LISTADO Y REGISTRO DE IDIOMA ─────────────────────

    def test_admin_puede_acceder_a_lista_idiomas(self):
        """Administrador puede acceder exitosamente al listado de idiomas."""
        self.client.login(username='admin_idioma', password='password123')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'configuracion/idiomas.html')

    def test_admin_puede_ver_formulario_nuevo_idioma(self):
        """Administrador puede ver el formulario y se incluye el parcial _form_fields."""
        self.client.login(username='admin_idioma', password='password123')
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'configuracion/idioma_form.html')
        self.assertTemplateUsed(response, 'configuracion/partials/_form_fields.html')

    def test_creacion_exitosa_de_idioma_valido(self):
        """Administrador registra un idioma válido y redirige a la lista."""
        self.client.login(username='admin_idioma', password='password123')
        datos = {
            'codigo': 'es',
            'nombre': 'Español',
            'es_principal': True,
            'activo': True
        }
        response = self.client.post(self.create_url, datos)
        self.assertRedirects(response, self.list_url)

        idioma = Idioma.objects.filter(codigo='es').first()
        self.assertIsNotNone(idioma)
        self.assertEqual(idioma.nombre, 'Español')
        self.assertTrue(idioma.es_principal)
        self.assertTrue(idioma.activo)

    def test_rechazo_de_idioma_con_codigo_duplicado(self):
        """No permite registrar dos idiomas con el mismo código (unique=True)."""
        Idioma.objects.create(codigo='es', nombre='Español', es_principal=True, activo=True)

        self.client.login(username='admin_idioma', password='password123')
        response = self.client.post(self.create_url, {
            'codigo': 'es',
            'nombre': 'Castellano',
            'es_principal': False,
            'activo': True
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(Idioma.objects.filter(codigo='es').count(), 1)

    # ── ESCENARIO 2: REGLA DE NEGOCIO — IDIOMA PRINCIPAL ÚNICO ────────

    def test_regla_idioma_principal_unico_al_crear(self):
        """
        Al registrar un nuevo idioma con es_principal=True, el idioma
        principal anterior se desmarca automáticamente a es_principal=False.
        """
        es = Idioma.objects.create(codigo='es', nombre='Español', es_principal=True, activo=True)
        self.assertTrue(es.es_principal)

        self.client.login(username='admin_idioma', password='password123')
        response = self.client.post(self.create_url, {
            'codigo': 'en',
            'nombre': 'English',
            'es_principal': True,
            'activo': True
        })
        self.assertRedirects(response, self.list_url)

        # Refrescar desde BD
        es.refresh_from_db()
        en = Idioma.objects.get(codigo='en')

        # Español ya no es principal, English ahora es principal
        self.assertFalse(es.es_principal)
        self.assertTrue(en.es_principal)
        self.assertEqual(Idioma.objects.filter(es_principal=True).count(), 1)

    def test_idioma_aparece_en_listado(self):
        """Idioma configurado se renderiza en la tabla con sus datos y badge."""
        Idioma.objects.create(codigo='es', nombre='Español', es_principal=True, activo=True)

        self.client.login(username='admin_idioma', password='password123')
        response = self.client.get(self.list_url)
        self.assertContains(response, 'es')
        self.assertContains(response, 'Español')
        self.assertContains(response, 'Principal')
        self.assertContains(response, 'Activo')


