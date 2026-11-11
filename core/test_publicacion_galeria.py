"""Paso 03d: la galería en las reglas de publicación y en el catálogo público.

La regla, en una frase: con galería gestionada manda la galería (hace falta su
fotografía principal y `imagen_url` deja de contar); mientras el producto no
la use, vale `imagen_url` como hasta ahora.

Esa regla vive en `Producto.tiene_imagen` y, como consulta, en
`ProductoQuerySet.con_imagen()`. Aquí se comprueba que las dos dicen siempre lo
mismo y que la respetan `clean()`, `completos()`, los formularios, la pantalla
de la galería y la tienda. Cada prueba usa un `MEDIA_ROOT` temporal.
"""

from decimal import Decimal

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from . import servicio_galeria as galeria
from .dashboard import ProductoForm
from .models import (
    MENSAJE_SIN_FOTOGRAFIA_PRINCIPAL,
    MENSAJE_SIN_IMAGEN,
    Coleccion,
    Producto,
    ProductoImagen,
)
from .test_galeria_vistas import crear_usuario
from .test_servicio_galeria import _Base, foto, fotos, url
from .vistas_galeria import MENSAJE_ULTIMA_FOTOGRAFIA

URL_ANTIGUA = "https://example.com/antigua.jpg"
IMAGEN_DE_RESPALDO = "img/coleccion-almadorada.webp"


def crear(nombre, **extra):
    """Producto en borrador (para poder montar su galería antes de publicarlo)."""
    coleccion, _ = Coleccion.objects.get_or_create(nombre="Alma Dorada")
    datos = {
        "coleccion": coleccion,
        "nombre": nombre,
        "precio": Decimal("1000000.00"),
        "es_borrador": True,
    }
    datos.update(extra)
    return Producto.objects.create(**datos)


def publicar(producto):
    """Publica sin pasar por `clean()`, como haría una carga directa de datos."""
    Producto.objects.filter(pk=producto.pk).update(activo=True, es_borrador=False)
    producto.refresh_from_db()
    return producto


class _Casos(_Base):
    """Los cinco estados posibles de «imagen» de un producto."""

    def setUp(self):
        super().setUp()
        # Sin galería: manda imagen_url.
        self.con_url = crear("Con URL", imagen_url=URL_ANTIGUA)
        self.sin_nada = crear("Sin nada")
        # Con galería gestionada: manda la fotografía principal.
        self.con_foto = crear("Con fotografía")
        galeria.agregar_archivos(self.con_foto, fotos(2))
        self.con_enlace = crear("Con enlace en la galería")
        galeria.agregar_url(self.con_enlace, url(7))
        # Galería gestionada que se quedó vacía: imagen_url ya NO cuenta.
        self.vaciada = crear("Vaciada", imagen_url=URL_ANTIGUA)
        unica = galeria.agregar_url(self.vaciada, url(8))
        galeria.eliminar_imagen(self.vaciada, unica.pk)
        self.vaciada.refresh_from_db()

        self.con_imagen = [self.con_url, self.con_foto, self.con_enlace]
        self.sin_imagen = [self.sin_nada, self.vaciada]


class ReglaDeImagenTests(_Casos):
    def test_tiene_imagen_en_cada_estado(self):
        for producto in self.con_imagen:
            with self.subTest(producto=producto.nombre):
                self.assertTrue(producto.tiene_imagen)
        for producto in self.sin_imagen:
            with self.subTest(producto=producto.nombre):
                self.assertFalse(producto.tiene_imagen)

    def test_la_consulta_y_la_propiedad_dicen_siempre_lo_mismo(self):
        todos = list(Producto.objects.all())
        self.assertEqual(len(todos), 6)  # los cinco casos y el producto de _Base

        self.assertEqual(
            set(Producto.objects.con_imagen()), {p for p in todos if p.tiene_imagen}
        )
        self.assertEqual(set(Producto.objects.con_imagen()), set(self.con_imagen))

    def test_completos_e_incompletos_se_reparten_todos_los_productos(self):
        completos = set(Producto.objects.completos())
        incompletos = set(Producto.objects.incompletos())

        self.assertEqual(completos, set(self.con_imagen))
        self.assertEqual(incompletos, set(Producto.objects.all()) - completos)

    def test_completos_sigue_exigiendo_nombre_codigo_y_precio(self):
        Producto.objects.filter(pk=self.con_foto.pk).update(precio=0)
        Producto.objects.filter(pk=self.con_enlace.pk).update(nombre="")
        Producto.objects.filter(pk=self.con_url.pk).update(codigo="")

        self.assertEqual(list(Producto.objects.completos()), [])

    def test_unas_filas_sin_principal_no_cuentan_como_imagen(self):
        # Estado que el servicio nunca deja, pero que la base de datos permite.
        ProductoImagen.objects.filter(producto=self.con_foto).update(es_principal=False)

        self.assertFalse(self.con_foto.tiene_imagen)
        self.assertNotIn(self.con_foto, Producto.objects.completos())

    def test_la_galeria_de_otro_producto_no_cuenta(self):
        self.assertFalse(self.sin_nada.tiene_imagen)
        self.assertIsNone(self.sin_nada.fotografia_principal)

    def test_un_producto_sin_guardar_no_tiene_fotografia_principal(self):
        nuevo = Producto(coleccion=self.con_url.coleccion, nombre="Nuevo", precio=1)

        self.assertIsNone(nuevo.fotografia_principal)
        self.assertFalse(nuevo.tiene_imagen)

    def test_fotografia_principal_sigue_los_cambios_de_la_galeria(self):
        primera, segunda = galeria.listar(self.con_foto)
        self.assertEqual(self.con_foto.fotografia_principal, primera)

        galeria.establecer_principal(self.con_foto, segunda.pk)

        self.assertEqual(self.con_foto.fotografia_principal, segunda)


class CleanTests(_Casos):
    def errores_al_publicar(self, producto):
        producto.activo, producto.es_borrador = True, False
        try:
            producto.full_clean()
        except ValidationError as error:
            return error.message_dict
        return {}

    def test_publicar_acepta_una_fotografia_principal_aunque_no_haya_url(self):
        for producto in (self.con_foto, self.con_enlace):
            with self.subTest(producto=producto.nombre):
                self.assertEqual(producto.imagen_url, "")
                self.assertEqual(self.errores_al_publicar(producto), {})

    def test_sin_galeria_sigue_valiendo_la_url_como_antes(self):
        self.assertEqual(self.errores_al_publicar(self.con_url), {})
        self.assertEqual(
            self.errores_al_publicar(self.sin_nada), {"imagen_url": [MENSAJE_SIN_IMAGEN]}
        )

    def test_con_la_galeria_vacia_la_url_antigua_ya_no_permite_publicar(self):
        self.assertEqual(self.vaciada.imagen_url, URL_ANTIGUA)

        errores = self.errores_al_publicar(self.vaciada)

        # El aviso es general: la galería no es un campo del formulario.
        self.assertEqual(errores, {NON_FIELD_ERRORS: [MENSAJE_SIN_FOTOGRAFIA_PRINCIPAL]})

    def test_un_borrador_o_un_inactivo_no_exigen_imagen(self):
        for producto in self.sin_imagen:
            for activo, es_borrador in ((True, True), (False, False), (False, True)):
                with self.subTest(producto=producto.nombre, activo=activo, borrador=es_borrador):
                    producto.activo, producto.es_borrador = activo, es_borrador
                    producto.full_clean()  # no debe lanzar


class FormularioDeProductoTests(_Casos):
    def datos(self, producto, **cambios):
        datos = {
            "nombre": producto.nombre,
            "coleccion": producto.coleccion_id,
            "precio": "1000000.00",
            "activo": "on",
        }
        datos.update(cambios)
        return datos

    def test_la_url_solo_aparece_mientras_no_haya_galeria(self):
        self.assertIn("imagen_url", ProductoForm().fields)
        for producto in (self.con_url, self.sin_nada):
            self.assertIn("imagen_url", ProductoForm(instance=producto).fields)
        for producto in (self.con_foto, self.con_enlace, self.vaciada):
            self.assertNotIn("imagen_url", ProductoForm(instance=producto).fields)

    def test_publica_un_producto_con_fotografia_principal_y_sin_url(self):
        formulario = ProductoForm(self.datos(self.con_foto), instance=self.con_foto)

        self.assertTrue(formulario.is_valid(), formulario.errors)
        formulario.save()

        self.con_foto.refresh_from_db()
        self.assertTrue(self.con_foto.es_publico)

    def test_no_publica_con_la_galeria_vacia_y_lo_explica(self):
        formulario = ProductoForm(
            self.datos(self.vaciada, imagen_url="https://example.com/otra.jpg"),
            instance=self.vaciada,
        )

        self.assertFalse(formulario.is_valid())
        self.assertEqual(formulario.non_field_errors(), [MENSAJE_SIN_FOTOGRAFIA_PRINCIPAL])

    def test_con_galeria_la_url_enviada_se_ignora_y_la_guardada_se_conserva(self):
        formulario = ProductoForm(
            self.datos(self.vaciada, es_borrador="on", imagen_url="https://example.com/otra.jpg"),
            instance=self.vaciada,
        )

        self.assertTrue(formulario.is_valid(), formulario.errors)
        formulario.save()

        self.vaciada.refresh_from_db()
        self.assertEqual(self.vaciada.imagen_url, URL_ANTIGUA)

    def test_sin_galeria_se_sigue_publicando_con_la_url(self):
        formulario = ProductoForm(
            self.datos(self.sin_nada, imagen_url=URL_ANTIGUA), instance=self.sin_nada
        )

        self.assertTrue(formulario.is_valid(), formulario.errors)


class PantallasTests(_Casos):
    def setUp(self):
        super().setUp()
        self.client.force_login(crear_usuario("administrador", "100000001", superusuario=True))
        self.url_panel = reverse("core:admin_section", kwargs={"seccion": "productos"})

    def test_el_panel_avisa_al_publicar_con_la_galeria_vacia(self):
        prefijo = f"productos-{self.vaciada.pk}"

        respuesta = self.client.post(
            self.url_panel,
            {
                "recurso": "productos",
                "accion": "edit",
                "registro": self.vaciada.pk,
                f"{prefijo}-nombre": self.vaciada.nombre,
                f"{prefijo}-coleccion": self.vaciada.coleccion_id,
                f"{prefijo}-precio": "1000000",
                f"{prefijo}-activo": "on",
                f"variantes-{self.vaciada.pk}-TOTAL_FORMS": "0",
                f"variantes-{self.vaciada.pk}-INITIAL_FORMS": "0",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, MENSAJE_SIN_FOTOGRAFIA_PRINCIPAL)
        self.vaciada.refresh_from_db()
        self.assertFalse(self.vaciada.es_publico)

    def test_el_formulario_de_edicion_avisa_al_publicar_con_la_galeria_vacia(self):
        respuesta = self.client.post(
            reverse("core:producto_editar", args=[self.vaciada.pk]),
            {
                "nombre": self.vaciada.nombre,
                "coleccion": self.vaciada.coleccion_id,
                "precio": "1000000",
                "activo": "on",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, MENSAJE_SIN_FOTOGRAFIA_PRINCIPAL)
        self.assertContains(respuesta, "Sin una fotografía principal no se puede publicar.")

    def test_la_activacion_en_bloque_usa_la_misma_regla(self):
        Producto.objects.update(activo=False, es_borrador=False)
        todos = list(Producto.objects.values_list("pk", flat=True))

        self.client.post(
            self.url_panel,
            {"recurso": "productos", "accion": "bulk", "estado": "1", "registros": todos},
        )

        self.assertEqual(
            set(Producto.objects.filter(activo=True)), set(self.con_imagen)
        )

    def test_el_bloque_avisa_mientras_la_tienda_usa_la_url_antigua(self):
        aviso = "La tienda muestra por ahora la «URL de la imagen» de la ficha."

        con_url = self.client.get(reverse("core:producto_editar", args=[self.con_url.pk]))
        con_foto = self.client.get(reverse("core:producto_editar", args=[self.con_foto.pk]))

        self.assertContains(con_url, aviso)
        self.assertContains(con_url, 'name="imagen_url"')
        self.assertNotContains(con_foto, aviso)
        self.assertNotContains(con_foto, 'name="imagen_url"')


class UltimaFotografiaTests(_Base):
    """Desde la pantalla, un producto publicado no puede quedarse sin fotografía."""

    def setUp(self):
        super().setUp()
        self.client.force_login(crear_usuario("administrador", "100000001", superusuario=True))
        self.producto = crear("Anillo Aurora")
        self.url = reverse("core:producto_galeria", args=[self.producto.pk])

    def eliminar(self, imagen_id):
        self.client.cookies.pop("messages", None)
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(self.url, {"accion": "eliminar", "imagen": imagen_id})
        return [m.message for m in respuesta.wsgi_request._messages]  # pylint: disable=protected-access

    def test_no_elimina_la_unica_fotografia_de_un_producto_publicado(self):
        unica = galeria.agregar_archivos(self.producto, [foto()])[0]
        publicar(self.producto)

        mensajes = self.eliminar(unica.pk)

        self.assertEqual(mensajes, [MENSAJE_ULTIMA_FOTOGRAFIA])
        self.assertEqual(self.filas(), [unica])
        self.assertEqual(len(self.archivos_en_disco()), 3)
        self.assertTrue(self.producto.tiene_imagen)

    def test_si_elimina_la_unica_fotografia_de_un_borrador(self):
        unica = galeria.agregar_archivos(self.producto, [foto()])[0]

        mensajes = self.eliminar(unica.pk)

        self.assertEqual(mensajes, ["Se eliminó la fotografía."])
        self.assertEqual(self.filas(), [])
        self.assertEqual(self.archivos_en_disco(), [])

    def test_con_dos_fotografias_deja_eliminar_una_pero_no_la_ultima(self):
        primera, segunda = galeria.agregar_archivos(self.producto, fotos(2))
        publicar(self.producto)

        self.assertEqual(self.eliminar(primera.pk), ["Se eliminó la fotografía."])
        self.assertEqual(self.eliminar(segunda.pk), [MENSAJE_ULTIMA_FOTOGRAFIA])

        self.assertEqual(self.filas(), [segunda])
        self.assertTrue(ProductoImagen.objects.get(pk=segunda.pk).es_principal)

    def test_un_identificador_ajeno_recibe_su_propio_aviso(self):
        galeria.agregar_archivos(self.producto, [foto()])
        publicar(self.producto)
        ajena = galeria.agregar_url(crear("Otro"), url(1))

        mensajes = self.eliminar(ajena.pk)

        self.assertEqual(mensajes, [galeria.MENSAJE_NO_PERTENECE])
        self.assertTrue(ProductoImagen.objects.filter(pk=ajena.pk).exists())


class CatalogoPublicoTests(_Casos):
    def setUp(self):
        super().setUp()
        Producto.objects.filter(pk=self.producto.pk).delete()  # el de _Base, sin imagen
        for producto in (*self.con_imagen, *self.sin_imagen):
            publicar(producto)

    def test_imagen_catalogo_en_cada_estado(self):
        principal = galeria.principal(self.con_foto)

        self.assertEqual(self.con_url.imagen_catalogo, URL_ANTIGUA)
        self.assertEqual(self.con_foto.imagen_catalogo, principal.archivo_detalle.url)
        self.assertEqual(self.con_enlace.imagen_catalogo, url(7))
        self.assertEqual(self.sin_nada.imagen_catalogo, "")
        self.assertEqual(self.vaciada.imagen_catalogo, "")

    def test_la_tienda_muestra_la_fotografia_principal_de_cada_galeria(self):
        Producto.objects.filter(pk__in=[p.pk for p in self.sin_imagen]).delete()
        _, segunda = galeria.listar(self.con_foto)
        galeria.establecer_principal(self.con_foto, segunda.pk)

        respuesta = self.client.get(reverse("core:inicio"))

        # Cada imagen sale dos veces: en la tarjeta y en el buscador de la cabecera.
        self.assertContains(respuesta, f'src="{segunda.archivo_detalle.url}"', count=2)
        self.assertContains(respuesta, f'src="{url(7)}"', count=2)
        self.assertContains(respuesta, f'src="{URL_ANTIGUA}"', count=2)

    def test_una_galeria_vacia_no_recurre_a_la_url_antigua(self):
        Producto.objects.exclude(pk=self.vaciada.pk).delete()

        respuesta = self.client.get(reverse("core:inicio"))

        self.assertContains(respuesta, self.vaciada.nombre)
        self.assertNotContains(respuesta, URL_ANTIGUA)
        self.assertContains(respuesta, IMAGEN_DE_RESPALDO)

    def test_las_fotografias_de_la_portada_se_leen_con_una_sola_consulta(self):
        for numero in range(3):
            galeria.agregar_archivos(publicar(crear(f"Extra {numero}")), [foto()])

        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(reverse("core:inicio"))

        self.assertEqual(len(respuesta.context["productos"]), 4)
        a_la_galeria = [c["sql"] for c in consultas if "core_productoimagen" in c["sql"]]
        self.assertEqual(len(a_la_galeria), 1, a_la_galeria)

    def test_con_la_precarga_no_se_consulta_producto_por_producto(self):
        productos = list(Producto.objects.con_fotografia_principal())

        with self.assertNumQueries(0):
            imagenes = {p.nombre: p.imagen_catalogo for p in productos}
            con_imagen = {p.nombre for p in productos if p.tiene_imagen}

        self.assertEqual(con_imagen, {p.nombre for p in self.con_imagen})
        self.assertEqual(imagenes[self.vaciada.nombre], "")
