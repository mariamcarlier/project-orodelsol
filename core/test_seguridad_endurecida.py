"""Endurecimiento de seguridad: métodos HTTP, IDs manipulados y CSRF.

Complementa —sin duplicar— ``core/test_autorizacion_vistas.py``, que ya
cubre la matriz de 6 perfiles de usuario × 8 endpoints. Este archivo
cierra los vacíos detectados en la auditoría final:

1. Métodos HTTP incorrectos (PUT/PATCH/DELETE) en crear/editar/eliminar
   productos y colecciones, incluido el bypass DELETE de
   ``ColeccionDeleteView``.
2. Identificadores inexistentes y con formato inválido, verificando que
   la base de datos NO cambia cuando la solicitud debe ser rechazada.
3. Protección CSRF con ``Client(enforce_csrf_checks=True)`` en los
   endpoints de creación, edición y eliminación.

Todas las pruebas corren sobre la base temporal de Django.
No se modifica la base de datos de desarrollo.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import resolve, reverse

from .models import Coleccion, Producto
from .test_autorizacion_vistas import (
    _crear_coleccion_sola,
    _crear_producto,
    _crear_usuario,
    _datos_coleccion_validos,
    _datos_producto_validos,
)

User = get_user_model()

METODOS_NO_PERMITIDOS = ("PUT", "PATCH", "DELETE")

ENDPOINTS_ESCRITURA = (
    "core:producto_crear",
    "core:producto_editar",
    "core:producto_eliminar",
    "core:coleccion_crear",
    "core:coleccion_editar",
    "core:coleccion_eliminar",
)

ENDPOINTS_TODOS = ENDPOINTS_ESCRITURA + (
    "core:producto_listar",
    "core:coleccion_listar",
)


def _url_con_pk_inexistente(nombre_url, pk=999999):
    """URL válida con un pk numérico, reemplazado por texto si se pide."""
    return reverse(nombre_url, args=[pk])


def _url_con_formato_invalido(nombre_url, fragmento):
    """Construye la URL sustituyendo el segmento del pk por ``fragmento``.

    Evita hardcodear la estructura de las rutas en el test.
    """
    url = _url_con_pk_inexistente(nombre_url)
    return url.replace("/999999/", f"/{fragmento}/")


class _SuperusuarioBase(TestCase):
    """Base con superusuario logueado para aislar rechazos de método/ID."""

    def setUp(self):
        self.super = _crear_usuario(
            "super_seg", "superseg@t.co", "910000001", is_superuser=True,
        )
        self.client.force_login(self.super)


# =====================================================================
# 1. MÉTODOS HTTP INCORRECTOS
# =====================================================================


class MetodosHttpIncorrectosTests(_SuperusuarioBase):
    """PUT/PATCH/DELETE deben rechazarse (405) sin efectos en la BD."""

    # ---------------- Productos ----------------

    def test_producto_crear_rechaza_put_sin_efecto(self):
        url = reverse("core:producto_crear")
        antes = Producto.objects.count()
        r = self.client.put(url)
        self.assertEqual(r.status_code, 405)
        self.assertEqual(Producto.objects.count(), antes)

    def test_producto_crear_rechaza_patch_sin_efecto(self):
        url = reverse("core:producto_crear")
        antes = Producto.objects.count()
        r = self.client.patch(url)
        self.assertEqual(r.status_code, 405)
        self.assertEqual(Producto.objects.count(), antes)

    def test_producto_crear_rechaza_delete_sin_efecto(self):
        url = reverse("core:producto_crear")
        antes = Producto.objects.count()
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 405)
        self.assertEqual(Producto.objects.count(), antes)

    def test_producto_editar_rechaza_put_sin_efecto(self):
        producto = _crear_producto()
        url = reverse("core:producto_editar", args=[producto.pk])
        r = self.client.put(url)
        self.assertEqual(r.status_code, 405)
        producto.refresh_from_db()
        self.assertEqual(producto.nombre, "Anillo Auth")

    def test_producto_editar_rechaza_patch_sin_efecto(self):
        producto = _crear_producto()
        url = reverse("core:producto_editar", args=[producto.pk])
        r = self.client.patch(url)
        self.assertEqual(r.status_code, 405)
        producto.refresh_from_db()
        self.assertEqual(producto.nombre, "Anillo Auth")

    def test_producto_editar_rechaza_delete_sin_efecto(self):
        producto = _crear_producto()
        url = reverse("core:producto_editar", args=[producto.pk])
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 405)
        producto.refresh_from_db()
        self.assertEqual(producto.nombre, "Anillo Auth")

    def test_producto_eliminar_rechaza_put_sin_efecto(self):
        producto = _crear_producto()
        url = reverse("core:producto_eliminar", args=[producto.pk])
        r = self.client.put(url)
        self.assertEqual(r.status_code, 405)
        self.assertTrue(Producto.objects.filter(pk=producto.pk).exists())

    def test_producto_eliminar_rechaza_delete_sin_efecto(self):
        producto = _crear_producto()
        url = reverse("core:producto_eliminar", args=[producto.pk])
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 405)
        self.assertTrue(Producto.objects.filter(pk=producto.pk).exists())

    def test_get_producto_crear_no_escribe(self):
        """GET con querystring no debe crear ni modificar nada."""
        url = reverse("core:producto_crear") + "?nombre=Hacked&precio=1"
        antes = Producto.objects.count()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Producto.objects.count(), antes)

    # ---------------- Colecciones ----------------

    def test_coleccion_crear_rechaza_put_sin_efecto(self):
        url = reverse("core:coleccion_crear")
        antes = Coleccion.objects.count()
        r = self.client.put(url)
        self.assertEqual(r.status_code, 405)
        self.assertEqual(Coleccion.objects.count(), antes)

    def test_coleccion_crear_rechaza_patch_sin_efecto(self):
        url = reverse("core:coleccion_crear")
        antes = Coleccion.objects.count()
        r = self.client.patch(url)
        self.assertEqual(r.status_code, 405)
        self.assertEqual(Coleccion.objects.count(), antes)

    def test_coleccion_crear_rechaza_delete_sin_efecto(self):
        url = reverse("core:coleccion_crear")
        antes = Coleccion.objects.count()
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 405)
        self.assertEqual(Coleccion.objects.count(), antes)

    def test_coleccion_editar_rechaza_put_sin_efecto(self):
        col = _crear_coleccion_sola()
        url = reverse("core:coleccion_editar", args=[col.pk])
        r = self.client.put(url)
        self.assertEqual(r.status_code, 405)
        col.refresh_from_db()
        self.assertEqual(col.nombre, "Col-Borrable")

    def test_coleccion_editar_rechaza_patch_sin_efecto(self):
        col = _crear_coleccion_sola()
        url = reverse("core:coleccion_editar", args=[col.pk])
        r = self.client.patch(url)
        self.assertEqual(r.status_code, 405)
        col.refresh_from_db()
        self.assertEqual(col.nombre, "Col-Borrable")

    def test_coleccion_editar_rechaza_delete_sin_efecto(self):
        col = _crear_coleccion_sola()
        url = reverse("core:coleccion_editar", args=[col.pk])
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 405)
        col.refresh_from_db()
        self.assertEqual(col.nombre, "Col-Borrable")

    def test_coleccion_eliminar_rechaza_put_sin_efecto(self):
        col = _crear_coleccion_sola()
        url = reverse("core:coleccion_eliminar", args=[col.pk])
        r = self.client.put(url)
        self.assertEqual(r.status_code, 405)
        self.assertTrue(Coleccion.objects.filter(pk=col.pk).exists())

    def test_coleccion_eliminar_rechaza_patch_sin_efecto(self):
        col = _crear_coleccion_sola()
        url = reverse("core:coleccion_eliminar", args=[col.pk])
        r = self.client.patch(url)
        self.assertEqual(r.status_code, 405)
        self.assertTrue(Coleccion.objects.filter(pk=col.pk).exists())

    def test_coleccion_eliminar_rechaza_delete_directo(self):
        """Una petición DELETE no debe saltarse la confirmación."""
        col = _crear_coleccion_sola()
        url = reverse("core:coleccion_eliminar", args=[col.pk])
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 405)
        self.assertTrue(Coleccion.objects.filter(pk=col.pk).exists())

    def test_coleccion_listar_rechaza_put(self):
        url = reverse("core:coleccion_listar")
        r = self.client.put(url)
        self.assertEqual(r.status_code, 405)

    def test_get_coleccion_crear_no_escribe(self):
        url = reverse("core:coleccion_crear") + "?nombre=Hacked"
        antes = Coleccion.objects.count()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Coleccion.objects.count(), antes)

    # ---------------- Orden: autorización antes que método HTTP --------

    def test_anonimo_put_producto_crear_recibe_login(self):
        """Sin sesión, la respuesta es de autenticación (302), no 405."""
        url = reverse("core:producto_crear")
        r = Client().put(url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.url)

    def test_staff_sin_permiso_put_recibe_405(self):
        """Con sesión pero sin permiso, el método se rechaza (405).

        El orden es: autenticación (staff) -> método HTTP -> permisos
        del modelo dentro de la vista; un PUT nunca llega a la vista.
        """
        staff = _crear_usuario(
            "staff_noperm", "snp@t.co", "910000002", is_staff=True,
        )
        cliente = Client()
        cliente.force_login(staff)
        r = cliente.put(reverse("core:producto_crear"))
        self.assertEqual(r.status_code, 405)


# =====================================================================
# 2. IDENTIFICADORES INEXISTENTES Y MANIPULADOS
# =====================================================================


class IdsManipuladosTests(_SuperusuarioBase):
    """IDs inexistentes o con formato inválido => 404 y BD intacta."""

    # ---------------- Producto: editar ----------------

    def test_editar_producto_inexistente_get_404(self):
        url = reverse("core:producto_editar", args=[999999])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_editar_producto_inexistente_post_404_sin_efecto(self):
        col = Coleccion.objects.create(nombre="Col-Ids", temporada="2026")
        url = reverse("core:producto_editar", args=[999999])
        datos = _datos_producto_validos(col.pk)
        antes = Producto.objects.count()
        r = self.client.post(url, datos)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Producto.objects.count(), antes)

    def test_editar_producto_pk_cero_404(self):
        url = reverse("core:producto_editar", args=[0])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_editar_producto_formato_abc_404(self):
        url = _url_con_formato_invalido("core:producto_editar", "abc")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_editar_producto_formato_negativo_404(self):
        url = _url_con_formato_invalido("core:producto_editar", "-1")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    # ---------------- Producto: eliminar ----------------

    def test_eliminar_producto_formato_abc_404_sin_efecto(self):
        producto = _crear_producto()
        url = _url_con_formato_invalido("core:producto_eliminar", "abc")
        antes = Producto.objects.count()
        r = self.client.post(url)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Producto.objects.count(), antes)
        self.assertTrue(Producto.objects.filter(pk=producto.pk).exists())

    def test_eliminar_producto_pk_cero_404(self):
        producto = _crear_producto()
        url = reverse("core:producto_eliminar", args=[0])
        antes = Producto.objects.count()
        r = self.client.post(url)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Producto.objects.count(), antes)
        self.assertTrue(Producto.objects.filter(pk=producto.pk).exists())

    # ---------------- Colecciones: editar ----------------

    def test_editar_coleccion_inexistente_get_404(self):
        url = reverse("core:coleccion_editar", args=[999999])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_editar_coleccion_inexistente_post_404_sin_efecto(self):
        url = reverse("core:coleccion_editar", args=[999999])
        antes = Coleccion.objects.count()
        r = self.client.post(url, _datos_coleccion_validos("Nunca"))
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Coleccion.objects.count(), antes)
        self.assertFalse(Coleccion.objects.filter(nombre="Nunca").exists())

    def test_editar_coleccion_formato_abc_404(self):
        url = _url_con_formato_invalido("core:coleccion_editar", "abc")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_editar_coleccion_pk_cero_404(self):
        url = reverse("core:coleccion_editar", args=[0])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    # ---------------- Colecciones: eliminar ----------------

    def test_eliminar_coleccion_inexistente_post_404(self):
        col = _crear_coleccion_sola()
        url = reverse("core:coleccion_eliminar", args=[999999])
        antes = Coleccion.objects.count()
        r = self.client.post(url)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Coleccion.objects.count(), antes)
        self.assertTrue(Coleccion.objects.filter(pk=col.pk).exists())

    def test_eliminar_coleccion_inexistente_get_404(self):
        url = reverse("core:coleccion_eliminar", args=[999999])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_eliminar_coleccion_formato_abc_404(self):
        url = _url_con_formato_invalido("core:coleccion_eliminar", "abc")
        r = self.client.post(url)
        self.assertEqual(r.status_code, 404)

    # ---------------- Alcance por objeto (sin efectos cruzados) ---------

    def test_editar_producto_no_modifica_a_otro_producto(self):
        col = Coleccion.objects.create(nombre="Col-Alcance", temporada="2026")
        a = Producto.objects.create(
            coleccion=col, nombre="Producto A", precio=100000,
            imagen_url="http://example.com/a.jpg",
        )
        b = Producto.objects.create(
            coleccion=col, nombre="Producto B", precio=200000,
            imagen_url="http://example.com/b.jpg",
        )
        url = reverse("core:producto_editar", args=[a.pk])
        datos = _datos_producto_validos(col.pk)
        datos["nombre"] = "Producto A editado"
        r = self.client.post(url, datos)
        self.assertEqual(r.status_code, 302)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.nombre, "Producto A editado")
        self.assertEqual(b.nombre, "Producto B")

    def test_editar_producto_no_toca_colecciones(self):
        producto = _crear_producto()
        col = producto.coleccion
        nombre_antes = col.nombre
        url = reverse("core:producto_editar", args=[producto.pk])
        datos = _datos_producto_validos(col.pk)
        datos["nombre"] = "Solo producto"
        r = self.client.post(url, datos)
        self.assertEqual(r.status_code, 302)
        col.refresh_from_db()
        self.assertEqual(col.nombre, nombre_antes)

    def test_editar_coleccion_no_modifica_a_otra_coleccion(self):
        a = Coleccion.objects.create(nombre="Col Uno", temporada="2026")
        b = Coleccion.objects.create(nombre="Col Dos", temporada="2026")
        url = reverse("core:coleccion_editar", args=[a.pk])
        datos = _datos_coleccion_validos("Col Uno editada")
        r = self.client.post(url, datos)
        self.assertEqual(r.status_code, 302)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.nombre, "Col Uno editada")
        self.assertEqual(b.nombre, "Col Dos")


# =====================================================================
# 3. PROTECCIÓN CSRF
# =====================================================================


class CsrfProteccionTests(TestCase):
    """CSRF activo en endpoints de creación, edición y eliminación."""

    def setUp(self):
        self.super = _crear_usuario(
            "super_csrf", "supercsrf@t.co", "920000001", is_superuser=True,
        )
        # Cliente que realmente exige el token (no lo desactiva).
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.super)

    def _obtener_token(self, url_pagina_con_formulario):
        """GET de una página con {% csrf_token %} y devuelve el token."""
        r = self.client.get(url_pagina_con_formulario)
        self.assertEqual(r.status_code, 200)
        self.assertIn("csrftoken", self.client.cookies)
        return self.client.cookies["csrftoken"].value

    def _post_con_token(self, url, datos=None, desde=None):
        """POST con token CSRF válido extraído de una página real."""
        token = self._obtener_token(desde)
        payload = dict(datos or {})
        payload["csrfmiddlewaretoken"] = token
        return self.client.post(url, payload)

    # ---------------- Guardas de configuración ----------------

    def test_middleware_csrf_configurado(self):
        """CsrfViewMiddleware debe seguir en MIDDLEWARE (no se desactivó)."""
        self.assertIn(
            "django.middleware.csrf.CsrfViewMiddleware",
            settings.MIDDLEWARE,
        )

    def test_ningun_endpoint_esta_csrf_exempt(self):
        """Ninguna vista de productos/colecciones declara csrf_exempt."""
        sin_pk = {
            "core:producto_listar",
            "core:producto_crear",
            "core:coleccion_listar",
            "core:coleccion_crear",
        }
        for nombre in ENDPOINTS_TODOS:
            with self.subTest(url=nombre):
                args = [] if nombre in sin_pk else [1]
                vista = resolve(reverse(nombre, args=args)).func
                self.assertFalse(
                    getattr(vista, "csrf_exempt", False),
                    f"{nombre} no debe estar marcada como csrf_exempt",
                )

    # ---------------- POST sin token => 403 y sin efecto ----------------

    def test_crear_producto_sin_token_403_sin_efecto(self):
        col = Coleccion.objects.create(nombre="Col-Csrf", temporada="2026")
        antes = Producto.objects.count()
        r = self.client.post(
            reverse("core:producto_crear"), _datos_producto_validos(col.pk),
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Producto.objects.count(), antes)

    def test_editar_producto_sin_token_403_sin_efecto(self):
        producto = _crear_producto()
        url = reverse("core:producto_editar", args=[producto.pk])
        datos = _datos_producto_validos(producto.coleccion.pk)
        datos["nombre"] = "Hackeado"
        r = self.client.post(url, datos)
        self.assertEqual(r.status_code, 403)
        producto.refresh_from_db()
        self.assertEqual(producto.nombre, "Anillo Auth")

    def test_eliminar_producto_sin_token_403_sin_efecto(self):
        producto = _crear_producto()
        url = reverse("core:producto_eliminar", args=[producto.pk])
        r = self.client.post(url)
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Producto.objects.filter(pk=producto.pk).exists())

    def test_crear_coleccion_sin_token_403_sin_efecto(self):
        antes = Coleccion.objects.count()
        r = self.client.post(
            reverse("core:coleccion_crear"), _datos_coleccion_validos(),
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Coleccion.objects.count(), antes)

    def test_editar_coleccion_sin_token_403_sin_efecto(self):
        col = _crear_coleccion_sola()
        url = reverse("core:coleccion_editar", args=[col.pk])
        r = self.client.post(
            url, _datos_coleccion_validos("Col Hackeada"),
        )
        self.assertEqual(r.status_code, 403)
        col.refresh_from_db()
        self.assertEqual(col.nombre, "Col-Borrable")

    def test_eliminar_coleccion_sin_token_403_sin_efecto(self):
        col = _crear_coleccion_sola()
        url = reverse("core:coleccion_eliminar", args=[col.pk])
        r = self.client.post(url)
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Coleccion.objects.filter(pk=col.pk).exists())

    # ---------------- POST con token => flujo normal ----------------

    def test_crear_producto_con_token_funciona(self):
        col = Coleccion.objects.create(nombre="Col-Csrf2", temporada="2026")
        url = reverse("core:producto_crear")
        r = self._post_con_token(
            url, _datos_producto_validos(col.pk),
            desde=url,
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Producto.objects.filter(nombre="Anillo Nuevo").exists())

    def test_editar_producto_con_token_funciona(self):
        producto = _crear_producto()
        url = reverse("core:producto_editar", args=[producto.pk])
        datos = _datos_producto_validos(producto.coleccion.pk)
        datos["nombre"] = "Anillo Editado Con Token"
        r = self._post_con_token(url, datos, desde=url)
        self.assertEqual(r.status_code, 302)
        producto.refresh_from_db()
        self.assertEqual(producto.nombre, "Anillo Editado Con Token")

    def test_eliminar_producto_con_token_funciona(self):
        producto = _crear_producto()
        url = reverse("core:producto_eliminar", args=[producto.pk])
        # La página de listado también emite {% csrf_token %}.
        r = self._post_con_token(
            url, desde=reverse("core:producto_listar"),
        )
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Producto.objects.filter(pk=producto.pk).exists())

    def test_crear_coleccion_con_token_funciona(self):
        url = reverse("core:coleccion_crear")
        r = self._post_con_token(
            url, _datos_coleccion_validos("Col Con Token"), desde=url,
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Coleccion.objects.filter(nombre="Col Con Token").exists())

    def test_editar_coleccion_con_token_funciona(self):
        col = _crear_coleccion_sola()
        url = reverse("core:coleccion_editar", args=[col.pk])
        r = self._post_con_token(
            url, _datos_coleccion_validos("Col Editada Con Token"), desde=url,
        )
        self.assertEqual(r.status_code, 302)
        col.refresh_from_db()
        self.assertEqual(col.nombre, "Col Editada Con Token")

    def test_eliminar_coleccion_con_token_funciona(self):
        col = _crear_coleccion_sola()
        url = reverse("core:coleccion_eliminar", args=[col.pk])
        r = self._post_con_token(
            url, desde=reverse("core:coleccion_listar"),
        )
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Coleccion.objects.filter(pk=col.pk).exists())

    def test_crear_producto_con_token_pero_datos_invalidos_revalida(self):
        """El token deja pasar hasta la validación del formulario."""
        url = reverse("core:producto_crear")
        r = self._post_con_token(
            url, {"nombre": ""}, desde=url,  # nombre vacío => inválido
        )
        self.assertEqual(r.status_code, 200)  # vuelve a mostrar el form
        self.assertFalse(Producto.objects.filter(nombre="").exists())

    # ---------------- Capas: anonimato y permisos después del token ----

    def test_anonimo_sin_token_recibe_403_csrf(self):
        """Sin sesión Y sin token, CSRF rechaza antes que la vista."""
        cliente = Client(enforce_csrf_checks=True)
        r = cliente.post(reverse("core:producto_crear"), {})
        self.assertEqual(r.status_code, 403)

    def test_anonimo_con_token_recibe_redirect_login(self):
        """Con token válido, manda la capa de autenticación (302)."""
        cliente = Client(enforce_csrf_checks=True)
        # El token se obtiene de una página pública con formulario
        # (la de login), porque /productos/nuevo/ redirige sin sesión.
        token = self._obtener_token_cliente(
            cliente, reverse("core:iniciar_sesion"),
        )
        r = cliente.post(
            reverse("core:producto_crear"),
            {"csrfmiddlewaretoken": token},
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.url)

    def test_staff_sin_permiso_con_token_recibe_403(self):
        """Con token válido pero sin permiso, manda la autorización."""
        from django.utils.crypto import get_random_string

        staff = _crear_usuario(
            "staff_csrf", "scsrf@t.co", "920000002", is_staff=True,
        )
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(staff)
        # Cookie y token coincidentes (mismo mecanismo que el middleware
        # valida); /login/ no sirve aquí porque redirige a usuarios
        # autenticados y /productos/nuevo/ devuelve 403 sin permiso.
        token = get_random_string(32)
        cliente.cookies["csrftoken"] = token
        r = cliente.post(
            reverse("core:producto_crear"),
            {"csrfmiddlewaretoken": token},
        )
        self.assertEqual(r.status_code, 403)

    def _obtener_token_cliente(self, cliente, url_pagina):
        """Versión de ``_obtener_token`` para un cliente externo."""
        r = cliente.get(url_pagina)
        self.assertEqual(r.status_code, 200)
        self.assertIn("csrftoken", cliente.cookies)
        return cliente.cookies["csrftoken"].value
