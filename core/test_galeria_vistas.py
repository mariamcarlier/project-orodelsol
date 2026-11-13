"""Pantalla de la galería de un producto (Paso 03c): `core.vistas_galeria`.

Qué se comprueba aquí:
- Quién puede usar la galería (personal con `core.change_producto`) y cómo.
- Que cada acción de la pantalla llega al servicio y deja el resultado esperado.
- Que el bloque aparece en las dos pantallas: formulario de edición y panel.

Las reglas de la galería (máximo, principal única, orden) ya se prueban en
`core/test_servicio_galeria.py`; aquí solo se comprueba que la pantalla las
respeta y muestra sus mensajes. Cada prueba usa un `MEDIA_ROOT` temporal.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from . import servicio_galeria as galeria
from .models import Producto, ProductoImagen
from .servicio_galeria import MAX_IMAGENES_POR_PRODUCTO
from .test_servicio_galeria import _Base, crear_producto, foto, fotos, url

DATOS_DE_USUARIO = {
    "tipo_documento": "CC",
    "fecha_nacimiento": date(1990, 1, 1),
    "telefono": "3001234567",
}


def crear_usuario(nombre, documento, *, personal=False, superusuario=False, permisos=()):
    """Usuario de prueba; `permisos` son nombres clave de permisos de Producto."""
    usuarios = get_user_model().objects
    crear = usuarios.create_superuser if superusuario else usuarios.create_user
    usuario = crear(
        username=nombre,
        password="clave-segura-42",
        email=f"{nombre}@example.com",
        documento=documento,
        is_staff=personal or superusuario,
        **DATOS_DE_USUARIO,
    )
    tipo = ContentType.objects.get_for_model(Producto)
    for clave in permisos:
        usuario.user_permissions.add(Permission.objects.get(codename=clave, content_type=tipo))
    return get_user_model().objects.get(pk=usuario.pk)  # sin la caché de permisos


def archivo_que_no_es_imagen(nombre="foto.jpg"):
    return SimpleUploadedFile(nombre, b"esto no es una fotografia", content_type="image/jpeg")


class _BasePantalla(_Base):
    """Producto con `MEDIA_ROOT` temporal y un superusuario con la sesión iniciada."""

    def setUp(self):
        super().setUp()
        self.client.force_login(crear_usuario("administrador", "100000001", superusuario=True))
        self.url = reverse("core:producto_galeria", args=[self.producto.pk])
        self.url_editar = reverse("core:producto_editar", args=[self.producto.pk])

    def enviar(self, accion, **datos):
        # Los avisos de un envío anterior que nadie leyó no deben contarse en este.
        self.client.cookies.pop("messages", None)
        return self.client.post(self.url, {"accion": accion, **datos})

    def mensajes(self, respuesta):
        return [(m.level_tag, m.message) for m in get_messages(respuesta.wsgi_request)]

    def ids(self):
        return [fila.pk for fila in self.filas()]

    def principal(self):
        return galeria.principal(self.producto).pk

    def assertVuelveALaFicha(self, respuesta):
        self.assertRedirects(
            respuesta, f"{self.url_editar}#galeria", fetch_redirect_response=False
        )

    def assertUnSoloError(self, respuesta, fragmento):
        mensajes = self.mensajes(respuesta)
        self.assertEqual([nivel for nivel, _ in mensajes], ["error"])
        self.assertIn(fragmento, mensajes[0][1])


# ---------------------------------------------------------------------------
# Quién puede usar la galería
# ---------------------------------------------------------------------------


class AutorizacionTests(_Base):
    def setUp(self):
        super().setUp()
        self.url = reverse("core:producto_galeria", args=[self.producto.pk])

    def subir(self, cliente=None):
        return (cliente or self.client).post(
            self.url, {"accion": "subir", "fotografias": [foto()]}
        )

    def assertNoSeGuardoNada(self):
        self.assertEqual(self.filas(), [])
        self.assertEqual(self.archivos_en_disco(), [])

    def test_anonimo_va_al_inicio_de_sesion_y_no_sube_nada(self):
        respuesta = self.subir()

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login", respuesta.url)
        self.assertNoSeGuardoNada()

    def test_cliente_sin_ser_personal_no_puede(self):
        self.client.force_login(crear_usuario("cliente", "100000002"))

        respuesta = self.subir()

        self.assertIn(respuesta.status_code, (302, 403))
        self.assertNoSeGuardoNada()

    def test_personal_sin_permiso_de_cambiar_recibe_403(self):
        permisos = ("view_producto", "add_producto", "delete_producto")
        self.client.force_login(
            crear_usuario("vendedor", "100000003", personal=True, permisos=permisos)
        )

        respuesta = self.subir()

        self.assertEqual(respuesta.status_code, 403)
        self.assertNoSeGuardoNada()

    def test_personal_con_permiso_de_cambiar_puede(self):
        self.client.force_login(
            crear_usuario("editor", "100000004", personal=True, permisos=("change_producto",))
        )

        respuesta = self.subir()

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(len(self.filas()), 1)

    def test_get_devuelve_405(self):
        self.client.force_login(crear_usuario("administrador", "100000005", superusuario=True))

        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_un_producto_que_no_existe_devuelve_404(self):
        self.client.force_login(crear_usuario("administrador", "100000006", superusuario=True))

        respuesta = self.client.post(
            reverse("core:producto_galeria", args=[99999]),
            {"accion": "subir", "fotografias": [foto()]},
        )

        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(self.archivos_en_disco(), [])

    def test_una_accion_desconocida_devuelve_403(self):
        self.client.force_login(crear_usuario("administrador", "100000007", superusuario=True))

        for accion in ("", "borrar_todo", None):
            with self.subTest(accion=accion):
                datos = {} if accion is None else {"accion": accion}
                self.assertEqual(self.client.post(self.url, datos).status_code, 403)

    def test_sin_token_csrf_se_rechaza(self):
        estricto = Client(enforce_csrf_checks=True)
        estricto.force_login(crear_usuario("administrador", "100000008", superusuario=True))

        respuesta = self.subir(estricto)

        self.assertEqual(respuesta.status_code, 403)
        self.assertNoSeGuardoNada()


# ---------------------------------------------------------------------------
# Acciones
# ---------------------------------------------------------------------------


class SubirTests(_BasePantalla):
    def test_sube_una_fotografia_y_vuelve_a_la_ficha(self):
        respuesta = self.enviar("subir", fotografias=[foto()])

        self.assertVuelveALaFicha(respuesta)
        self.assertEqual(self.mensajes(respuesta), [("success", "Se añadió 1 fotografía.")])
        self.assertEqual(len(self.filas()), 1)
        self.assertEqual(len(self.archivos_en_disco()), 3)
        self.assertGaleriaConsistente()

    def test_sube_varias_a_la_vez(self):
        respuesta = self.enviar("subir", fotografias=fotos(3))

        self.assertEqual(self.mensajes(respuesta), [("success", "Se añadieron 3 fotografías.")])
        self.assertEqual(len(self.filas()), 3)
        self.assertGaleriaConsistente()

    def test_sin_elegir_archivos_avisa_y_no_guarda(self):
        respuesta = self.enviar("subir")

        self.assertVuelveALaFicha(respuesta)
        self.assertUnSoloError(respuesta, "Selecciona al menos una fotografía")
        self.assertEqual(self.filas(), [])

    def test_un_archivo_que_no_es_imagen_cancela_todo_el_envio(self):
        respuesta = self.enviar("subir", fotografias=[foto(), archivo_que_no_es_imagen()])

        self.assertVuelveALaFicha(respuesta)
        self.assertUnSoloError(respuesta, "«foto.jpg»")
        self.assertEqual(self.filas(), [])
        self.assertEqual(self.archivos_en_disco(), [])

    def test_no_deja_pasar_del_maximo(self):
        galeria.agregar_archivos(self.producto, fotos(MAX_IMAGENES_POR_PRODUCTO - 1))

        respuesta = self.enviar("subir", fotografias=fotos(2))

        self.assertUnSoloError(respuesta, f"como máximo {MAX_IMAGENES_POR_PRODUCTO}")
        self.assertEqual(len(self.filas()), MAX_IMAGENES_POR_PRODUCTO - 1)
        self.assertGaleriaConsistente()

    def test_un_fallo_del_disco_se_avisa_sin_error_500(self):
        with self.assertLogs("core.vistas_galeria", level="ERROR"):
            with self.settings(MEDIA_ROOT=str(self.media / "no-es-carpeta.txt" / "x")):
                (self.media / "no-es-carpeta.txt").write_bytes(b"")
                respuesta = self.enviar("subir", fotografias=[foto()])

        self.assertVuelveALaFicha(respuesta)
        self.assertUnSoloError(respuesta, "No se pudieron guardar los archivos")
        self.assertEqual(self.filas(), [])


class AgregarUrlTests(_BasePantalla):
    def test_anade_una_direccion_web(self):
        respuesta = self.enviar("url", url=url(1))

        self.assertVuelveALaFicha(respuesta)
        self.assertEqual(self.mensajes(respuesta)[0][0], "success")
        self.assertEqual([fila.url for fila in self.filas()], [url(1)])
        self.assertEqual(self.archivos_en_disco(), [])

    def test_rechaza_lo_que_no_es_http(self):
        for direccion in ("", "javascript:alert(1)", "ftp://example.com/a.jpg", "no es una url"):
            with self.subTest(direccion=direccion):
                respuesta = self.enviar("url", url=direccion)

                self.assertEqual(self.mensajes(respuesta)[0][0], "error")
        self.assertEqual(self.filas(), [])


class OrganizarTests(_BasePantalla):
    """La pantalla envía posiciones 1, 2, 3...: una por fotografía."""

    def setUp(self):
        super().setUp()
        galeria.agregar_archivos(self.producto, fotos(3))
        self.a, self.b, self.c = self.filas()

    def organizar(self, posiciones=None, principal=None):
        """Envía el formulario completo, cambiando solo lo indicado."""
        datos = {f"posicion-{fila.pk}": lugar for lugar, fila in enumerate(self.filas(), start=1)}
        datos.update({f"posicion-{pk}": valor for pk, valor in (posiciones or {}).items()})
        datos["principal"] = principal if principal is not None else self.principal()
        return self.enviar("organizar", **datos)

    def test_cambia_la_fotografia_principal_sin_moverla(self):
        respuesta = self.organizar(principal=self.c.pk)

        self.assertVuelveALaFicha(respuesta)
        self.assertEqual(self.mensajes(respuesta)[0][0], "success")
        self.assertEqual(self.principal(), self.c.pk)
        self.assertEqual(self.ids(), [self.a.pk, self.b.pk, self.c.pk])
        self.assertGaleriaConsistente()

    def test_bajar_la_primera_a_la_posicion_2(self):
        # Los otros números no cambian: «2» queda repetido en el formulario.
        self.organizar({self.a.pk: 2})

        self.assertEqual(self.ids(), [self.b.pk, self.a.pk, self.c.pk])
        self.assertGaleriaConsistente()

    def test_bajar_la_primera_a_la_ultima_posicion(self):
        self.organizar({self.a.pk: 3})

        self.assertEqual(self.ids(), [self.b.pk, self.c.pk, self.a.pk])

    def test_subir_la_ultima_a_la_posicion_1(self):
        self.organizar({self.c.pk: 1})

        self.assertEqual(self.ids(), [self.c.pk, self.a.pk, self.b.pk])

    def test_intercambiar_dos(self):
        self.organizar({self.a.pk: 3, self.c.pk: 1})

        self.assertEqual(self.ids(), [self.c.pk, self.b.pk, self.a.pk])

    def test_un_numero_mayor_que_la_galeria_la_manda_al_final(self):
        self.organizar({self.a.pk: 99})

        self.assertEqual(self.ids(), [self.b.pk, self.c.pk, self.a.pk])

    def test_la_ultima_con_un_numero_mayor_no_cuenta_como_cambio(self):
        respuesta = self.organizar({self.c.pk: 99})

        self.assertEqual(
            self.mensajes(respuesta), [("success", "No había cambios que guardar en la galería.")]
        )
        self.assertEqual(self.ids(), [self.a.pk, self.b.pk, self.c.pk])

    def test_orden_y_principal_en_el_mismo_envio(self):
        self.organizar({self.c.pk: 1}, principal=self.b.pk)

        self.assertEqual(self.ids(), [self.c.pk, self.a.pk, self.b.pk])
        self.assertEqual(self.principal(), self.b.pk)
        self.assertGaleriaConsistente()

    def test_sin_cambios_lo_dice_y_no_toca_nada(self):
        antes = self.estado()

        respuesta = self.organizar()

        self.assertEqual(
            self.mensajes(respuesta), [("success", "No había cambios que guardar en la galería.")]
        )
        self.assertEqual(self.estado(), antes)

    def test_una_posicion_que_no_es_un_numero_no_cambia_nada(self):
        antes = self.estado()

        for valor in ("", "abc", "1.5", "2 3"):
            with self.subTest(valor=valor):
                respuesta = self.organizar({self.a.pk: valor}, principal=self.c.pk)

                self.assertUnSoloError(respuesta, "número entero")
                self.assertEqual(self.estado(), antes)

    def test_una_posicion_menor_que_1_no_cambia_nada(self):
        antes = self.estado()

        for valor in ("0", "-1"):
            with self.subTest(valor=valor):
                respuesta = self.organizar({self.a.pk: valor})

                self.assertUnSoloError(respuesta, "entre 1 y 3")
                self.assertEqual(self.estado(), antes)

    def test_una_principal_de_otro_producto_cancela_tambien_el_orden(self):
        ajena = galeria.agregar_archivos(crear_producto("Anillo Brisa"), [foto()])[0]
        antes = self.estado()

        respuesta = self.organizar({self.a.pk: 3}, principal=ajena.pk)

        self.assertUnSoloError(respuesta, "no pertenece a este producto")
        self.assertEqual(self.estado(), antes)
        self.assertTrue(ProductoImagen.objects.get(pk=ajena.pk).es_principal)

    def test_las_posiciones_de_fotografias_ajenas_se_ignoran(self):
        ajena = galeria.agregar_archivos(crear_producto("Anillo Brisa"), fotos(2))[1]

        self.organizar({ajena.pk: 1})

        self.assertEqual(ProductoImagen.objects.get(pk=ajena.pk).orden, 1)
        self.assertEqual(self.ids(), [self.a.pk, self.b.pk, self.c.pk])


class EliminarTests(_BasePantalla):
    def setUp(self):
        super().setUp()
        galeria.agregar_archivos(self.producto, fotos(2))
        self.a, self.b = self.filas()

    def test_elimina_la_fotografia_y_sus_archivos(self):
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.enviar("eliminar", imagen=self.a.pk)

        self.assertVuelveALaFicha(respuesta)
        self.assertEqual(self.mensajes(respuesta), [("success", "Se eliminó la fotografía.")])
        self.assertEqual(self.ids(), [self.b.pk])
        self.assertEqual(self.principal(), self.b.pk)
        self.assertEqual(len(self.archivos_en_disco()), 3)
        self.assertGaleriaConsistente()

    def test_no_elimina_una_fotografia_de_otro_producto(self):
        ajena = galeria.agregar_archivos(crear_producto("Anillo Brisa"), [foto()])[0]

        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.enviar("eliminar", imagen=ajena.pk)

        self.assertUnSoloError(respuesta, "no pertenece a este producto")
        self.assertTrue(ProductoImagen.objects.filter(pk=ajena.pk).exists())
        self.assertEqual(len(self.archivos_en_disco()), 9)

    def test_un_identificador_inventado_no_rompe_nada(self):
        for valor in ("", "abc", "99999", "1 OR 1=1"):
            with self.subTest(valor=valor):
                respuesta = self.enviar("eliminar", imagen=valor)

                self.assertUnSoloError(respuesta, "no pertenece a este producto")
        self.assertEqual(len(self.filas()), 2)


class DestinoTests(_BasePantalla):
    """Después de cada acción se vuelve a la pantalla de origen, sin salir del sitio."""

    def test_sin_indicacion_vuelve_a_la_ficha_del_producto(self):
        self.assertVuelveALaFicha(self.enviar("url", url=url(1)))

    def test_respeta_una_direccion_de_este_sitio(self):
        panel = "/panel-admin/productos/?page=2&galeria=7#registros"

        respuesta = self.enviar("url", url=url(1), siguiente=panel)

        self.assertRedirects(respuesta, panel, fetch_redirect_response=False)

    def test_ignora_direcciones_de_otros_sitios(self):
        for destino in (
            "https://evil.example/robo",
            "//evil.example/robo",
            "javascript:alert(1)",
            "http:evil.example",
        ):
            with self.subTest(destino=destino):
                respuesta = self.enviar("url", url="no vale", siguiente=destino)

                self.assertVuelveALaFicha(respuesta)


# ---------------------------------------------------------------------------
# El bloque en las dos pantallas
# ---------------------------------------------------------------------------


class BloqueEnElFormularioTests(_BasePantalla):
    def test_al_editar_muestra_miniaturas_posiciones_y_principal(self):
        galeria.agregar_archivos(self.producto, fotos(2))
        galeria.agregar_url(self.producto, url(9))
        primera, segunda, tercera = self.filas()
        galeria.establecer_principal(self.producto, segunda.pk)

        respuesta = self.client.get(self.url_editar)

        self.assertContains(respuesta, 'id="galeria"')
        self.assertContains(respuesta, f"3 de {MAX_IMAGENES_POR_PRODUCTO} fotografías")
        self.assertContains(respuesta, f'src="{primera.archivo_miniatura.url}"')
        self.assertContains(respuesta, f'src="{segunda.archivo_miniatura.url}"')
        self.assertContains(respuesta, f'src="{url(9)}"')
        for lugar, fila in enumerate((primera, segunda, tercera), start=1):
            self.assertContains(
                respuesta, f'name="posicion-{fila.pk}" value="{lugar}"', count=1
            )
        self.assertContains(
            respuesta, f'<input type="radio" name="principal" value="{segunda.pk}" checked>',
            html=True,
        )
        self.assertContains(respuesta, 'name="principal"', count=3)
        self.assertContains(respuesta, 'name="accion" value="eliminar"', count=3)

    def test_el_texto_alternativo_nombra_al_producto(self):
        galeria.agregar_archivos(self.producto, fotos(2))

        respuesta = self.client.get(self.url_editar)

        self.assertContains(respuesta, f'alt="Fotografía 1 de {self.producto.nombre}"')
        self.assertContains(respuesta, f'alt="Fotografía 2 de {self.producto.nombre}"')

    def test_un_borrador_sin_nombre_se_nombra_por_su_codigo(self):
        # Desde PROD-12 un borrador puede guardarse sin nombre.
        galeria.agregar_archivos(self.producto, fotos(1))
        Producto.objects.filter(pk=self.producto.pk).update(nombre="", es_borrador=True)
        self.producto.refresh_from_db()

        respuesta = self.client.get(self.url_editar)

        self.assertContains(respuesta, f'alt="Fotografía 1 de {self.producto.codigo}"')
        self.assertNotContains(respuesta, 'alt="Fotografía 1 de "')

    def test_el_formulario_de_subida_envia_archivos_a_la_galeria(self):
        respuesta = self.client.get(self.url_editar)

        self.assertContains(respuesta, f'action="{self.url}" enctype="multipart/form-data"')
        self.assertContains(respuesta, 'name="fotografias"')
        self.assertContains(respuesta, "multiple")
        self.assertContains(respuesta, "Hasta 10 MB por fotografía y 30 MB por envío")
        self.assertContains(respuesta, f"Puedes añadir {MAX_IMAGENES_POR_PRODUCTO} más.")
        self.assertContains(respuesta, "Este producto todavía no tiene fotografías.")

    def test_el_bloque_no_queda_dentro_del_formulario_del_producto(self):
        # HTML no admite formularios anidados: la galería va después de cerrarlo.
        html = self.client.get(self.url_editar).content.decode()

        inicio = html.index('class="producto-form"')
        cierre = html.index("</form>", inicio)
        self.assertGreater(html.index('id="galeria"'), cierre)

    def test_con_la_galeria_llena_el_selector_sigue_visible_pero_deshabilitado(self):
        """Decisión de la revisión: el campo no desaparece, se deshabilita.

        Quien administra tiene que ver que el límite existe y por qué no puede
        subir más. El servidor sigue rechazando igual un envío forzado; eso lo
        prueban las pruebas del servicio y las de la pantalla.
        """
        galeria.agregar_archivos(self.producto, fotos(MAX_IMAGENES_POR_PRODUCTO))

        respuesta = self.client.get(self.url_editar)

        self.assertContains(respuesta, "La galería está completa.")
        self.assertContains(respuesta, "Elimina una fotografía para poder añadir otra.")
        self.assertContains(respuesta, "El selector está deshabilitado")
        self.assertContains(respuesta, 'name="fotografias"', count=1)
        # El atributo `disabled` va en el propio campo, no en otro control.
        campo = respuesta.content.decode().split('name="fotografias"', 1)[1].split(">", 1)[0]
        self.assertIn("disabled", campo)
        # Añadir una dirección tampoco está disponible con la galería llena.
        self.assertNotContains(respuesta, 'name="accion" value="url"')

    def test_al_crear_un_producto_explica_que_las_fotografias_van_despues(self):
        respuesta = self.client.get(reverse("core:producto_crear"))

        self.assertContains(respuesta, "Las fotografías se añaden después de guardar el producto")
        self.assertNotContains(respuesta, 'id="galeria"')
        self.assertNotContains(respuesta, 'name="fotografias"')

    def test_el_aviso_de_la_ultima_accion_se_pinta_dentro_del_bloque(self):
        respuesta = self.client.post(
            self.url,
            {"accion": "subir", "fotografias": [archivo_que_no_es_imagen("anillo.jpg")]},
            follow=True,
        )

        self.assertContains(respuesta, "galeria-admin__aviso--error", count=1)
        self.assertContains(respuesta, "«anillo.jpg»")
        self.assertContains(respuesta, 'role="alert"')

    def test_un_envio_con_errores_del_producto_conserva_la_galeria(self):
        galeria.agregar_archivos(self.producto, [foto()])

        respuesta = self.client.post(self.url_editar, {"nombre": "", "precio": "0"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, f"1 de {MAX_IMAGENES_POR_PRODUCTO} fotografías")


class BloqueEnElPanelTests(_BasePantalla):
    def setUp(self):
        super().setUp()
        self.url_panel = reverse("core:admin_section", kwargs={"seccion": "productos"})

    def test_cada_producto_trae_su_galeria_en_la_ficha(self):
        otro = crear_producto("Anillo Brisa")
        galeria.agregar_archivos(self.producto, fotos(2))
        miniatura = self.filas()[0].archivo_miniatura.url

        respuesta = self.client.get(self.url_panel)

        self.assertContains(respuesta, "css/galeria-admin.css")
        self.assertContains(respuesta, f"Fotografías (2 de {MAX_IMAGENES_POR_PRODUCTO})", count=1)
        self.assertContains(respuesta, f"Fotografías (0 de {MAX_IMAGENES_POR_PRODUCTO})", count=1)
        self.assertContains(respuesta, f'src="{miniatura}"')
        self.assertContains(respuesta, f'id="galeria-{self.producto.pk}"')
        self.assertContains(respuesta, f'id="galeria-{otro.pk}"')
        self.assertContains(
            respuesta, f'action="{self.url}" enctype="multipart/form-data"', count=1
        )

    def test_las_acciones_vuelven_a_la_misma_pagina_del_panel(self):
        respuesta = self.client.get(self.url_panel, {"q": "Anillo", "page": "1"})

        esperado = f"{self.url_panel}?q=Anillo&amp;page=1&amp;galeria={self.producto.pk}#registros"
        self.assertContains(respuesta, f'name="siguiente" value="{esperado}"')

    def test_al_volver_reabre_la_ficha_con_la_galeria_desplegada(self):
        otro = crear_producto("Anillo Brisa")

        respuesta = self.client.get(self.url_panel, {"galeria": self.producto.pk})

        fila = next(
            f for f in respuesta.context["recurso"]["filas"] if f["objeto"] == self.producto
        )
        otra = next(f for f in respuesta.context["recurso"]["filas"] if f["objeto"] == otro)
        self.assertTrue(fila["abrir_edicion"] and fila["abrir_galeria"])
        self.assertFalse(otra["abrir_edicion"] or otra["abrir_galeria"])
        self.assertContains(respuesta, "data-dashboard-dialog-autoshow", count=1)
        self.assertContains(respuesta, '<details class="dashboard-galeria" open>', count=1)

    def test_sin_el_parametro_no_abre_ninguna_ficha(self):
        respuesta = self.client.get(self.url_panel)

        self.assertNotContains(respuesta, "data-dashboard-dialog-autoshow")
        self.assertNotContains(respuesta, '<details class="dashboard-galeria" open>')

    def test_el_ciclo_completo_desde_el_panel(self):
        siguiente = f"{self.url_panel}?galeria={self.producto.pk}#registros"

        respuesta = self.client.post(
            self.url,
            {"accion": "subir", "fotografias": [foto()], "siguiente": siguiente},
            follow=True,
        )

        self.assertEqual(respuesta.redirect_chain, [(siguiente, 302)])
        self.assertContains(respuesta, "galeria-admin__aviso--success", count=1)
        self.assertContains(respuesta, "Se añadió 1 fotografía.")
        self.assertContains(respuesta, f"Fotografías (1 de {MAX_IMAGENES_POR_PRODUCTO})")

    def test_las_galerias_de_la_pagina_se_leen_con_una_sola_consulta(self):
        for numero in range(4):
            galeria.agregar_archivos(crear_producto(f"Anillo {numero}"), fotos(2))

        with CaptureQueriesContext(connection) as consultas:
            self.client.get(self.url_panel)

        a_la_galeria = [c["sql"] for c in consultas if "core_productoimagen" in c["sql"]]
        self.assertEqual(len(a_la_galeria), 1, a_la_galeria)

    def test_quien_solo_puede_ver_no_recibe_el_bloque(self):
        self.client.force_login(
            crear_usuario("lector", "100000020", personal=True, permisos=("view_producto",))
        )

        respuesta = self.client.get(self.url_panel)

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'class="galeria-admin"')
        self.assertNotContains(respuesta, "dashboard-galeria")
        self.assertNotContains(respuesta, 'name="fotografias"')

    def test_el_formulario_de_alta_avisa_de_que_las_fotografias_van_despues(self):
        respuesta = self.client.get(self.url_panel)

        self.assertContains(respuesta, "Las fotografías se añaden después de guardar")

    def test_otras_secciones_del_panel_no_cargan_la_galeria(self):
        respuesta = self.client.get(
            reverse("core:admin_section", kwargs={"seccion": "colecciones"})
        )

        self.assertNotContains(respuesta, "galeria-admin")
