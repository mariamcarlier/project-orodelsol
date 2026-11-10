"""Pruebas de autorización de las vistas tradicionales de Productos y Colecciones.

Verifica que las operaciones CRUD de productos y colecciones exijan
``is_staff`` y el permiso Django específico (``view``, ``add``, ``change``,
``delete``), de acuerdo con la política B aprobada.

Cada escenario se prueba para seis perfiles:
  1. Usuario anónimo.
  2. Cliente autenticado (no staff).
  3. Staff sin ningún permiso de modelo.
  4. Staff con permiso parcial (distinto al requerido).
  5. Staff con el permiso exacto requerido.
  6. Superusuario.

Todas las pruebas corren sobre la base temporal de Django.
No se modifica la base de datos de desarrollo.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from .models import Coleccion, Producto

User = get_user_model()

DATOS_BASE = {
    "tipo_documento": "CC",
    "fecha_nacimiento": date(1990, 1, 1),
    "telefono": "3001234567",
}


def _perm(codename, model_class):
    """Devuelve el Permission filtrado por codename Y ContentType del modelo."""
    ct = ContentType.objects.get_for_model(model_class)
    return Permission.objects.get(codename=codename, content_type=ct)


def _crear_usuario(username, email, documento, is_staff=False, is_superuser=False, perms=None):
    """Crea un usuario de prueba con permisos opcionales.

    ``perms`` es una lista de tuplas ``(codename, model_class)`` para
    identificar cada permiso de manera inequívoca.
    """
    if is_superuser:
        user = User.objects.create_superuser(
            username=username, password="clave-segura-42",
            email=email, documento=documento, **DATOS_BASE,
        )
    else:
        user = User.objects.create_user(
            username=username, password="clave-segura-42",
            email=email, documento=documento, is_staff=is_staff, **DATOS_BASE,
        )
    if perms:
        for codename, model_class in perms:
            user.user_permissions.add(_perm(codename, model_class))
        # Forzar recarga de caché de permisos.
        user = User.objects.get(pk=user.pk)
    return user


def _crear_producto():
    col = Coleccion.objects.create(nombre="Col-Auth-Test", temporada="2026")
    return Producto.objects.create(
        coleccion=col, nombre="Anillo Auth", precio=100000,
        imagen_url="http://example.com/img.jpg",
    )


def _crear_coleccion_sola():
    """Colección sin productos (se puede eliminar)."""
    return Coleccion.objects.create(nombre="Col-Borrable", temporada="2026")


def _datos_producto_validos(coleccion_pk):
    """Datos POST que cumplen todos los campos obligatorios de ProductoForm."""
    return {
        "nombre": "Anillo Nuevo",
        "coleccion": coleccion_pk,
        "precio": "150000.00",
        "imagen_url": "http://example.com/new.jpg",
        "codigo": "",
        "detalle": "",
        "descripcion": "",
    }


def _datos_coleccion_validos(nombre="Coleccion Nueva"):
    """Datos POST que cumplen todos los campos de ColeccionForm."""
    return {
        "nombre": nombre,
        "descripcion": "",
        "temporada": "",
        "imagen_url": "",
        "activa": "on",
    }


# =====================================================================
# PRODUCTOS — LISTAR
# =====================================================================

class ProductoListarAutorizacionTests(TestCase):
    """GET /productos/ — requiere is_staff + core.view_producto."""

    def setUp(self):
        self.url = reverse("core:producto_listar")

    def test_anonimo_redirige_a_login(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.url)

    def test_cliente_autenticado_denegado(self):
        user = _crear_usuario("cliente", "c@t.co", "800000001")
        self.client.force_login(user)
        r = self.client.get(self.url)
        self.assertIn(r.status_code, (302, 403))
        self.assertNotEqual(r.status_code, 200)

    def test_staff_sin_permisos_denegado(self):
        user = _crear_usuario("staff0", "s0@t.co", "800000002", is_staff=True)
        self.client.force_login(user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)

    def test_staff_con_view_producto_permitido(self):
        user = _crear_usuario(
            "staffv", "sv@t.co", "800000003",
            is_staff=True, perms=[("view_producto", Producto)],
        )
        self.client.force_login(user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_superusuario_permitido(self):
        user = _crear_usuario("super", "su@t.co", "800000004", is_superuser=True)
        self.client.force_login(user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_add_no_concede_view(self):
        """Tener add_producto no permite listar productos."""
        user = _crear_usuario(
            "staff_add", "sa@t.co", "800000005",
            is_staff=True, perms=[("add_producto", Producto)],
        )
        self.client.force_login(user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)


# =====================================================================
# PRODUCTOS — CREAR
# =====================================================================

class ProductoCrearAutorizacionTests(TestCase):
    """GET/POST /productos/nuevo/ — requiere is_staff + core.add_producto."""

    def setUp(self):
        self.url = reverse("core:producto_crear")
        self.col = Coleccion.objects.create(nombre="Col-Crear", temporada="2026")
        self.datos_post = _datos_producto_validos(self.col.pk)

    def test_anonimo_redirige_y_no_crea(self):
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.url)
        self.assertFalse(Producto.objects.filter(nombre="Anillo Nuevo").exists())

    def test_cliente_denegado_y_no_crea(self):
        user = _crear_usuario("cliente", "c@t.co", "800000011")
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertIn(r.status_code, (302, 403))
        self.assertFalse(Producto.objects.filter(nombre="Anillo Nuevo").exists())

    def test_staff_sin_add_denegado_y_no_crea(self):
        user = _crear_usuario(
            "staff_view", "svw@t.co", "800000012",
            is_staff=True, perms=[("view_producto", Producto)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Producto.objects.filter(nombre="Anillo Nuevo").exists())

    def test_staff_con_add_permitido(self):
        user = _crear_usuario(
            "staff_add", "sa@t.co", "800000013",
            is_staff=True, perms=[("add_producto", Producto)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Producto.objects.filter(nombre="Anillo Nuevo").exists())

    def test_superusuario_permitido(self):
        user = _crear_usuario("super", "su@t.co", "800000014", is_superuser=True)
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Producto.objects.filter(nombre="Anillo Nuevo").exists())

    def test_change_no_concede_add(self):
        """Tener change_producto no permite crear productos."""
        user = _crear_usuario(
            "staff_chg", "sc@t.co", "800000015",
            is_staff=True, perms=[("change_producto", Producto)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Producto.objects.filter(nombre="Anillo Nuevo").exists())

    def test_delete_no_concede_add(self):
        """Tener delete_producto no permite crear productos."""
        user = _crear_usuario(
            "staff_del", "sd@t.co", "800000016",
            is_staff=True, perms=[("delete_producto", Producto)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Producto.objects.filter(nombre="Anillo Nuevo").exists())


# =====================================================================
# PRODUCTOS — EDITAR
# =====================================================================

class ProductoEditarAutorizacionTests(TestCase):
    """GET/POST /productos/<pk>/editar/ — requiere is_staff + core.change_producto."""

    def setUp(self):
        self.producto = _crear_producto()
        self.url = reverse("core:producto_editar", args=[self.producto.pk])
        self.datos_post = {
            "nombre": "Nombre Cambiado",
            "coleccion": self.producto.coleccion.pk,
            "precio": "200000.00",
            "imagen_url": "http://example.com/edit.jpg",
            "codigo": self.producto.codigo,
            "detalle": "",
            "descripcion": "",
        }

    def test_anonimo_redirige_y_no_modifica(self):
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.url)
        self.producto.refresh_from_db()
        self.assertNotEqual(self.producto.nombre, "Nombre Cambiado")

    def test_cliente_denegado_y_no_modifica(self):
        user = _crear_usuario("cliente", "c@t.co", "800000021")
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertIn(r.status_code, (302, 403))
        self.producto.refresh_from_db()
        self.assertNotEqual(self.producto.nombre, "Nombre Cambiado")

    def test_staff_con_solo_add_denegado_y_no_modifica(self):
        user = _crear_usuario(
            "staff_add", "sa@t.co", "800000022",
            is_staff=True, perms=[("add_producto", Producto)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 403)
        self.producto.refresh_from_db()
        self.assertNotEqual(self.producto.nombre, "Nombre Cambiado")

    def test_staff_con_change_permitido(self):
        user = _crear_usuario(
            "staff_chg", "sc@t.co", "800000023",
            is_staff=True, perms=[("change_producto", Producto)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 302)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.nombre, "Nombre Cambiado")

    def test_superusuario_permitido(self):
        user = _crear_usuario("super", "su@t.co", "800000024", is_superuser=True)
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 302)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.nombre, "Nombre Cambiado")

    def test_delete_no_concede_change(self):
        """Tener delete_producto no permite editar productos."""
        user = _crear_usuario(
            "staff_del", "sd@t.co", "800000025",
            is_staff=True, perms=[("delete_producto", Producto)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 403)
        self.producto.refresh_from_db()
        self.assertNotEqual(self.producto.nombre, "Nombre Cambiado")


# =====================================================================
# PRODUCTOS — ELIMINAR
# =====================================================================

class ProductoEliminarAutorizacionTests(TestCase):
    """POST /productos/<pk>/eliminar/ — requiere is_staff + core.delete_producto."""

    def setUp(self):
        self.producto = _crear_producto()
        self.url = reverse("core:producto_eliminar", args=[self.producto.pk])

    def test_anonimo_no_puede_eliminar(self):
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.url)
        self.assertTrue(Producto.objects.filter(pk=self.producto.pk).exists())

    def test_get_devuelve_405(self):
        """GET a la URL de eliminar producto devuelve 405 (método no permitido)."""
        user = _crear_usuario("super", "su@t.co", "800000030", is_superuser=True)
        self.client.force_login(user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 405)
        self.assertTrue(Producto.objects.filter(pk=self.producto.pk).exists())

    def test_cliente_denegado_y_no_elimina(self):
        user = _crear_usuario("cliente", "c@t.co", "800000031")
        self.client.force_login(user)
        r = self.client.post(self.url)
        self.assertIn(r.status_code, (302, 403))
        self.assertTrue(Producto.objects.filter(pk=self.producto.pk).exists())

    def test_staff_sin_delete_denegado_y_no_elimina(self):
        user = _crear_usuario(
            "staff_view", "sv@t.co", "800000032",
            is_staff=True, perms=[("view_producto", Producto), ("change_producto", Producto)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Producto.objects.filter(pk=self.producto.pk).exists())

    def test_staff_con_delete_permitido(self):
        user = _crear_usuario(
            "staff_del", "sd@t.co", "800000033",
            is_staff=True, perms=[("delete_producto", Producto)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Producto.objects.filter(pk=self.producto.pk).exists())

    def test_superusuario_permitido(self):
        user = _crear_usuario("super", "su@t.co", "800000034", is_superuser=True)
        self.client.force_login(user)
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Producto.objects.filter(pk=self.producto.pk).exists())

    def test_pk_inexistente_devuelve_404(self):
        user = _crear_usuario("super", "su@t.co", "800000035", is_superuser=True)
        self.client.force_login(user)
        r = self.client.post(reverse("core:producto_eliminar", args=[99999]))
        self.assertEqual(r.status_code, 404)

    def test_change_no_concede_delete(self):
        """Tener change_producto no permite eliminar."""
        user = _crear_usuario(
            "staff_chg", "sc@t.co", "800000036",
            is_staff=True, perms=[("change_producto", Producto)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Producto.objects.filter(pk=self.producto.pk).exists())

    def test_add_no_concede_delete(self):
        """Tener add_producto no permite eliminar."""
        user = _crear_usuario(
            "staff_add", "sa@t.co", "800000037",
            is_staff=True, perms=[("add_producto", Producto)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Producto.objects.filter(pk=self.producto.pk).exists())


# =====================================================================
# COLECCIONES — LISTAR
# =====================================================================

class ColeccionListarAutorizacionTests(TestCase):
    """GET /colecciones/ — requiere is_staff + core.view_coleccion."""

    def setUp(self):
        self.url = reverse("core:coleccion_listar")

    def test_anonimo_redirige(self):
        r = self.client.get(self.url)
        self.assertIn(r.status_code, (302, 403))
        self.assertNotEqual(r.status_code, 200)

    def test_cliente_denegado(self):
        user = _crear_usuario("cliente", "c@t.co", "800000041")
        self.client.force_login(user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)

    def test_staff_sin_permisos_denegado(self):
        user = _crear_usuario("staff0", "s0@t.co", "800000042", is_staff=True)
        self.client.force_login(user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)

    def test_staff_con_view_coleccion_permitido(self):
        user = _crear_usuario(
            "staffv", "sv@t.co", "800000043",
            is_staff=True, perms=[("view_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_superusuario_permitido(self):
        user = _crear_usuario("super", "su@t.co", "800000044", is_superuser=True)
        self.client.force_login(user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_add_no_concede_view(self):
        """Tener add_coleccion no permite listar colecciones."""
        user = _crear_usuario(
            "staff_add", "sa@t.co", "800000045",
            is_staff=True, perms=[("add_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)


# =====================================================================
# COLECCIONES — CREAR
# =====================================================================

class ColeccionCrearAutorizacionTests(TestCase):
    """POST /colecciones/nueva/ — requiere is_staff + core.add_coleccion."""

    def setUp(self):
        self.url = reverse("core:coleccion_crear")
        self.datos_post = _datos_coleccion_validos()

    def test_anonimo_no_crea(self):
        r = self.client.post(self.url, self.datos_post)
        self.assertIn(r.status_code, (302, 403))
        self.assertFalse(Coleccion.objects.filter(nombre="Coleccion Nueva").exists())

    def test_cliente_denegado_y_no_crea(self):
        user = _crear_usuario("cliente", "c@t.co", "800000051")
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Coleccion.objects.filter(nombre="Coleccion Nueva").exists())

    def test_staff_sin_add_denegado_y_no_crea(self):
        user = _crear_usuario(
            "staffv", "sv@t.co", "800000052",
            is_staff=True, perms=[("view_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Coleccion.objects.filter(nombre="Coleccion Nueva").exists())

    def test_staff_con_add_permitido(self):
        user = _crear_usuario(
            "staffa", "sa@t.co", "800000053",
            is_staff=True, perms=[("add_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Coleccion.objects.filter(nombre="Coleccion Nueva").exists())

    def test_superusuario_permitido(self):
        user = _crear_usuario("super", "su@t.co", "800000054", is_superuser=True)
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Coleccion.objects.filter(nombre="Coleccion Nueva").exists())

    def test_change_no_concede_add(self):
        """Tener change_coleccion no permite crear colecciones."""
        user = _crear_usuario(
            "staff_chg", "sc@t.co", "800000055",
            is_staff=True, perms=[("change_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Coleccion.objects.filter(nombre="Coleccion Nueva").exists())

    def test_delete_no_concede_add(self):
        """Tener delete_coleccion no permite crear colecciones."""
        user = _crear_usuario(
            "staff_del", "sd@t.co", "800000056",
            is_staff=True, perms=[("delete_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Coleccion.objects.filter(nombre="Coleccion Nueva").exists())


# =====================================================================
# COLECCIONES — EDITAR
# =====================================================================

class ColeccionEditarAutorizacionTests(TestCase):
    """POST /colecciones/<pk>/editar/ — requiere is_staff + core.change_coleccion."""

    def setUp(self):
        self.col = _crear_coleccion_sola()
        self.url = reverse("core:coleccion_editar", args=[self.col.pk])
        self.datos_post = _datos_coleccion_validos("Nombre Editado")

    def test_anonimo_no_modifica(self):
        r = self.client.post(self.url, self.datos_post)
        self.assertIn(r.status_code, (302, 403))
        self.col.refresh_from_db()
        self.assertNotEqual(self.col.nombre, "Nombre Editado")

    def test_cliente_denegado_y_no_modifica(self):
        user = _crear_usuario("cliente", "c@t.co", "800000061")
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 403)
        self.col.refresh_from_db()
        self.assertNotEqual(self.col.nombre, "Nombre Editado")

    def test_staff_sin_change_denegado_y_no_modifica(self):
        user = _crear_usuario(
            "staffv", "sv@t.co", "800000062",
            is_staff=True, perms=[("view_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 403)
        self.col.refresh_from_db()
        self.assertNotEqual(self.col.nombre, "Nombre Editado")

    def test_staff_con_change_permitido(self):
        user = _crear_usuario(
            "staffc", "sc@t.co", "800000063",
            is_staff=True, perms=[("change_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 302)
        self.col.refresh_from_db()
        self.assertEqual(self.col.nombre, "Nombre Editado")

    def test_superusuario_permitido(self):
        user = _crear_usuario("super", "su@t.co", "800000064", is_superuser=True)
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 302)
        self.col.refresh_from_db()
        self.assertEqual(self.col.nombre, "Nombre Editado")

    def test_delete_no_concede_change(self):
        """Tener delete_coleccion no permite editar colecciones."""
        user = _crear_usuario(
            "staff_del", "sd@t.co", "800000065",
            is_staff=True, perms=[("delete_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 403)
        self.col.refresh_from_db()
        self.assertNotEqual(self.col.nombre, "Nombre Editado")

    def test_add_no_concede_change(self):
        """Tener add_coleccion no permite editar colecciones."""
        user = _crear_usuario(
            "staff_add", "sa@t.co", "800000066",
            is_staff=True, perms=[("add_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url, self.datos_post)
        self.assertEqual(r.status_code, 403)
        self.col.refresh_from_db()
        self.assertNotEqual(self.col.nombre, "Nombre Editado")


# =====================================================================
# COLECCIONES — ELIMINAR
# =====================================================================

class ColeccionEliminarAutorizacionTests(TestCase):
    """POST /colecciones/<pk>/eliminar/ — requiere is_staff + core.delete_coleccion."""

    def setUp(self):
        self.col = _crear_coleccion_sola()
        self.url = reverse("core:coleccion_eliminar", args=[self.col.pk])

    def test_anonimo_no_elimina(self):
        r = self.client.post(self.url)
        self.assertIn(r.status_code, (302, 403))
        self.assertTrue(Coleccion.objects.filter(pk=self.col.pk).exists())

    def test_cliente_denegado_y_no_elimina(self):
        user = _crear_usuario("cliente", "c@t.co", "800000071")
        self.client.force_login(user)
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Coleccion.objects.filter(pk=self.col.pk).exists())

    def test_staff_sin_delete_denegado_y_no_elimina(self):
        user = _crear_usuario(
            "staffv", "sv@t.co", "800000072",
            is_staff=True, perms=[("view_coleccion", Coleccion), ("change_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Coleccion.objects.filter(pk=self.col.pk).exists())

    def test_staff_con_delete_permitido(self):
        user = _crear_usuario(
            "staffd", "sd@t.co", "800000073",
            is_staff=True, perms=[("delete_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Coleccion.objects.filter(pk=self.col.pk).exists())

    def test_superusuario_permitido(self):
        user = _crear_usuario("super", "su@t.co", "800000074", is_superuser=True)
        self.client.force_login(user)
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Coleccion.objects.filter(pk=self.col.pk).exists())

    def test_get_muestra_confirmacion_con_permiso(self):
        """GET a eliminar colección muestra la página de confirmación (no elimina)."""
        user = _crear_usuario(
            "staffd", "sd@t.co", "800000075",
            is_staff=True, perms=[("delete_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Eliminar")
        # GET no debe eliminar.
        self.assertTrue(Coleccion.objects.filter(pk=self.col.pk).exists())

    def test_get_sin_permiso_denegado(self):
        user = _crear_usuario(
            "staffv", "sv@t.co", "800000076",
            is_staff=True, perms=[("view_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Coleccion.objects.filter(pk=self.col.pk).exists())

    def test_change_no_concede_delete(self):
        """Tener change_coleccion no permite eliminar."""
        user = _crear_usuario(
            "staff_chg", "sc@t.co", "800000077",
            is_staff=True, perms=[("change_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Coleccion.objects.filter(pk=self.col.pk).exists())

    def test_add_no_concede_delete(self):
        """Tener add_coleccion no permite eliminar."""
        user = _crear_usuario(
            "staff_add", "sa@t.co", "800000078",
            is_staff=True, perms=[("add_coleccion", Coleccion)],
        )
        self.client.force_login(user)
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Coleccion.objects.filter(pk=self.col.pk).exists())


# =====================================================================
# CATÁLOGO PÚBLICO (no debe verse afectado)
# =====================================================================

class CatalogoPublicoTests(TestCase):
    """La página de inicio (/) sigue siendo pública."""

    def test_inicio_accesible_sin_login(self):
        r = self.client.get(reverse("core:inicio"))
        self.assertEqual(r.status_code, 200)

    def test_inicio_no_exige_staff(self):
        user = _crear_usuario("cliente", "c@t.co", "800000081")
        self.client.force_login(user)
        r = self.client.get(reverse("core:inicio"))
        self.assertEqual(r.status_code, 200)
