"""Pantalla de carga de la galería: lo que el rediseño promete y el servidor cumple.

Aquí se comprueban las tres cosas que el rediseño agrega a la pantalla del Paso
03c, sin repetir lo que ya prueban `core/test_galeria_vistas.py` (acciones,
permisos y avisos) ni `core/test_servicio_galeria.py` (reglas del servicio):

1. La configuración que recibe el navegador es EXACTAMENTE la del servidor:
   mismos límites y mismos mensajes (`core/mensajes_galeria.py`). Así no se
   puede quedar un texto o un número desincronizado sin que falle una prueba.
2. Los controles del rediseño están, son accesibles y no rompen lo anterior:
   botones de orden con JavaScript y campos de posición sin él, aviso de cambios
   sin guardar, selector deshabilitado con la galería llena.
3. El servidor sigue aceptando el orden calculado por los botones y rechaza lo
   que el navegador también rechazaría: el contrato `posicion-<pk>` no cambió.
"""

import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from . import mensajes_galeria, servicio_galeria as galeria
from .imagenes import (
    FORMATOS_POR_EXTENSION,
    MAX_ANCHO_VISTA_PREVIA,
    MAX_BYTES_POR_ENVIO,
    MAX_BYTES_POR_IMAGEN,
    MAX_LADO_PX,
    MAX_PIXELES,
    MB,
)
from .servicio_galeria import MAX_IMAGENES_POR_PRODUCTO
from .test_galeria_vistas import _BasePantalla, archivo_que_no_es_imagen
from .test_servicio_galeria import foto, fotos, url


def configuracion_de(respuesta, producto):
    """Lee el JSON que la plantilla deja para `carga.js`."""
    html = respuesta.content.decode()
    inicio = html.index(f'<script id="galeria-config-{producto.pk}" type="application/json">')
    inicio = html.index(">", inicio) + 1
    fin = html.index("</script>", inicio)
    return json.loads(html[inicio:fin])


class ConfiguracionParaElNavegadorTests(_BasePantalla):
    """El navegador valida con los números y los textos del servidor, no con otros."""

    def test_los_limites_son_los_del_servidor(self):
        respuesta = self.client.get(self.url_editar)

        cfg = configuracion_de(respuesta, self.producto)

        self.assertEqual(cfg["maximo"], MAX_IMAGENES_POR_PRODUCTO)
        self.assertEqual(cfg["libres"], MAX_IMAGENES_POR_PRODUCTO)
        self.assertEqual(cfg["maximoPorImagen"], MAX_BYTES_POR_IMAGEN)
        self.assertEqual(cfg["maximoPorEnvio"], MAX_BYTES_POR_ENVIO)
        self.assertEqual(cfg["mbPorImagen"], MAX_BYTES_POR_IMAGEN // MB)
        self.assertEqual(cfg["mbPorEnvio"], MAX_BYTES_POR_ENVIO // MB)
        self.assertEqual(cfg["ladoMaximo"], MAX_LADO_PX)
        self.assertEqual(cfg["megapixelesMaximos"], MAX_PIXELES // 1_000_000)
        self.assertEqual(cfg["anchoVistaPrevia"], MAX_ANCHO_VISTA_PREVIA)
        self.assertEqual(cfg["tipos"], sorted(FORMATOS_POR_EXTENSION))

    def test_los_huecos_libres_bajan_con_las_fotografias_que_hay(self):
        galeria.agregar_archivos(self.producto, fotos(3))

        cfg = configuracion_de(self.client.get(self.url_editar), self.producto)

        self.assertEqual(cfg["libres"], MAX_IMAGENES_POR_PRODUCTO - 3)

    def test_los_mensajes_del_navegador_son_los_del_servidor(self):
        cfg = configuracion_de(self.client.get(self.url_editar), self.producto)

        self.assertEqual(cfg["mensajes"], mensajes_galeria.MENSAJES)
        self.assertEqual(cfg["etiquetaArchivo"], mensajes_galeria.ETIQUETA_ARCHIVO)

    def test_el_texto_que_el_servidor_dice_y_el_que_recibe_el_navegador_coinciden(self):
        """Un mismo rechazo se explica igual antes y después de enviar."""
        respuesta = self.client.post(
            self.url,
            {"accion": "subir", "fotografias": [archivo_que_no_es_imagen("anillo.jpg")]},
            follow=True,
        )
        cfg = configuracion_de(respuesta, self.producto)
        mensaje_servidor = [m.message for m in respuesta.context["messages"]]
        texto = mensaje_servidor[0]

        esperado = mensajes_galeria.error_de_archivo(
            "anillo.jpg", cfg["mensajes"]["no_imagen"]
        )
        self.assertEqual(texto, esperado)

    def test_el_mensaje_de_formato_no_permitido_lo_dice_el_servidor(self):
        """Un GIF de verdad: el navegador avisa con el texto del servidor.

        No basta con un archivo de texto llamado «.gif»: ese ni siquiera es una
        imagen y el servidor lo rechaza por otra razón. La prueba usa un GIF que
        Pillow sí abre, y confirma que el texto que el navegador adelanta es el
        mismo que el servidor termina diciendo.
        """
        galeria.agregar_archivos(self.producto, [foto()])
        respuesta = self.client.post(
            self.url, {"accion": "subir", "fotografias": [archivo_gif()]},
            follow=True,
        )

        texto = [m.message for m in respuesta.context["messages"]][0]
        esperado = mensajes_galeria.MENSAJES["formato"].format(formato="GIF")

        self.assertEqual(texto, mensajes_galeria.error_de_archivo("anillo.gif", esperado))
        # Y la plantilla que recibe el navegador produce exactamente esa frase.
        plantilla = configuracion_de(respuesta, self.producto)["mensajes"]["formato"]
        self.assertEqual(plantilla.format(formato="GIF"), esperado)

    def test_una_sola_galeria_por_pagina_no_repite_la_configuracion(self):
        """En el panel hay una galería por producto: cada una lleva la suya."""
        otro = self.producto.__class__.objects.create(
            coleccion=self.producto.coleccion,
            nombre="Anillo Brisa",
            precio=1000,
            imagen_url="https://example.com/brisa.jpg",
        )
        galeria.agregar_archivos(self.producto, fotos(2))

        panel = self.client.get(reverse("core:admin_section", kwargs={"seccion": "productos"}))
        html = panel.content.decode()

        self.assertEqual(html.count('<script id="galeria-config-'), 2)
        self.assertEqual(html.count(f'<script id="galeria-config-{self.producto.pk}"'), 1)
        self.assertEqual(html.count(f'<script id="galeria-config-{otro.pk}"'), 1)
        self.assertEqual(configuracion_de(panel, self.producto)["libres"], MAX_IMAGENES_POR_PRODUCTO - 2)


class ControlesDelRedisenoTests(_BasePantalla):
    """Lo nuevo de la pantalla, con lo que necesita un lector de pantalla."""

    def test_la_cabecera_explica_para_que_sirve(self):
        respuesta = self.client.get(self.url_editar)

        self.assertContains(respuesta, "Cargar imágenes del producto")
        self.assertContains(
            respuesta,
            "Agrega fotografías para mostrar los detalles de tus piezas.",
        )

    def test_la_zona_de_carga_anuncia_el_arrastre_y_el_boton(self):
        respuesta = self.client.get(self.url_editar)

        self.assertContains(respuesta, "Arrastra tus imágenes aquí")
        self.assertContains(respuesta, "O selecciona archivos desde tu dispositivo")
        self.assertContains(respuesta, "Seleccionar imágenes")
        self.assertContains(respuesta, "data-zona")
        # La anatomía del rediseño: un icono arriba y el botón dentro de la zona.
        self.assertContains(respuesta, "galeria-admin__zona-icono")

    def test_los_limites_se_leen_de_un_vistazo_y_son_los_del_servidor(self):
        respuesta = self.client.get(self.url_editar)

        self.assertContains(respuesta, "galeria-admin__limites")
        self.assertContains(respuesta, "Formatos</span> JPG, PNG o WebP")
        self.assertContains(
            respuesta,
            "Tamaño</span> Hasta 10 MB por fotografía y 30 MB por envío",
        )
        self.assertContains(respuesta, "Cantidad</span> 10 fotografías por producto")

    def test_la_vista_previa_tiene_su_titulo_y_su_contador(self):
        respuesta = self.client.get(self.url_editar)

        self.assertContains(respuesta, "Vista previa")
        self.assertContains(respuesta, "data-contador")
        self.assertContains(respuesta, "data-previa")

    def test_el_campo_de_archivo_es_accesible_pese_a_estar_visualmente_oculto(self):
        respuesta = self.client.get(self.url_editar)

        self.assertContains(respuesta, 'aria-describedby="galeria-limites-')
        self.assertContains(respuesta, 'accept="image/jpeg,image/png,image/webp"')
        self.assertContains(respuesta, "data-archivo")
        # La ayuda que describe el campo existe y tiene el id que se anuncia.
        self.assertContains(respuesta, f'id="galeria-limites-{self.producto.pk}"')

    def test_cada_foto_tiene_flechas_y_un_campo_de_respaldo_para_ordenar(self):
        galeria.agregar_archivos(self.producto, fotos(2))
        primera, segunda = self.filas()

        respuesta = self.client.get(self.url_editar)

        self.assertContains(respuesta, 'aria-label="Subir esta fotografía"', count=2)
        self.assertContains(respuesta, 'aria-label="Bajar esta fotografía"', count=2)
        for lugar, fila in enumerate((primera, segunda), start=1):
            self.assertContains(
                respuesta,
                f'type="number" name="posicion-{fila.pk}" value="{lugar}" data-posicion-campo',
                count=1,
            )
        # El campo es visible sin JavaScript; las flechas lo sustituyen con él.
        self.assertContains(respuesta, '<span>Posición</span>', count=2)
        self.assertContains(respuesta, 'min="1" max="2" step="1" inputmode="numeric" required', count=2)

    def test_la_principal_sigue_siendo_un_control_accesible(self):
        galeria.agregar_archivos(self.producto, fotos(2))
        primera, segunda = self.filas()

        respuesta = self.client.get(self.url_editar)

        self.assertContains(respuesta, 'type="radio" name="principal"', count=2)
        # La principal es la primera: marcada solo ella, y no la segunda.
        self.assertContains(respuesta, f'value="{primera.pk}" checked', count=1)
        campo = respuesta.content.decode().split(f'value="{segunda.pk}"', 1)[1].split(">", 1)[0]
        self.assertNotIn("checked", campo)

    def test_el_bloque_avisa_de_los_cambios_sin_guardar(self):
        galeria.agregar_archivos(self.producto, fotos(2))

        respuesta = self.client.get(self.url_editar)

        self.assertContains(respuesta, f'id="galeria-cambios-{self.producto.pk}"')
        self.assertContains(respuesta, 'role="status"')
        self.assertContains(respuesta, "data-estado-guardado")

    def test_la_galeria_guardada_ofrece_agregar_otra_tarjeta(self):
        galeria.agregar_archivos(self.producto, fotos(2))

        respuesta = self.client.get(self.url_editar)

        self.assertContains(respuesta, "galeria-admin__agregar")
        self.assertContains(respuesta, "Agregar otra")
        # Es una etiqueta del campo real: abre el selector sin JavaScript.
        etiqueta = respuesta.content.decode().split("galeria-admin__agregar-etiqueta", 1)[1]
        self.assertIn(f'for="galeria-archivos-{self.producto.pk}"', etiqueta.split(">", 1)[0])

    def test_con_la_galeria_llena_no_hay_tarjeta_de_agregar(self):
        galeria.agregar_archivos(self.producto, fotos(MAX_IMAGENES_POR_PRODUCTO))

        respuesta = self.client.get(self.url_editar)

        self.assertNotContains(respuesta, "Agregar otra")

    def test_eliminar_pide_confirmacion_sin_el_dialogo_del_navegador(self):
        galeria.agregar_archivos(self.producto, [foto()])

        respuesta = self.client.get(self.url_editar)

        self.assertNotContains(respuesta, "confirm(")
        self.assertContains(respuesta, "¿Eliminar esta foto?")
        self.assertContains(respuesta, "Sí, eliminar")

    def test_el_bloque_no_muestra_controles_que_no_tienen_sentido(self):
        """Cada estado enseña lo que corresponde: nada de botones de más."""
        html_vacio = self.client.get(self.url_editar).content.decode()
        # Sin fotos no hay nada que ordenar ni eliminar ni marcar como principal.
        self.assertNotIn('name="accion" value="organizar"', html_vacio)
        self.assertNotIn('name="accion" value="eliminar"', html_vacio)
        self.assertIn('name="accion" value="subir"', html_vacio)
        # La selección, el aviso de cambios y la confirmación empiezan ocultos.
        self.assertIn("data-seleccion hidden", html_vacio)
        self.assertIn('id="galeria-cambios-', html_vacio)

        galeria.agregar_archivos(self.producto, fotos(2))
        html_lleno = self.client.get(self.url_editar).content.decode()
        self.assertIn("data-confirmar hidden", html_lleno)
        self.assertEqual(html_lleno.count('name="accion" value="eliminar"'), 2)

    def test_el_bloque_no_se_oculta_ni_pierde_su_contenido(self):
        """Regresión: el atributo `hidden` de un aviso no puede ir en el bloque.

        Un `data-mensajes-id` sobrante en el contenedor hacía que el JavaScript
        del bloque se lo tragara y la galería desapareciera al cargar la página.
        """
        galeria.agregar_archivos(self.producto, fotos(2))

        html = self.client.get(self.url_editar).content.decode()
        # La etiqueta de apertura completa del bloque, con todos sus atributos.
        desde = html.rindex("<div", 0, html.index(f'id="galeria-{self.producto.pk}"'))
        etiqueta = html[desde:html.index(">", desde)]
        self.assertNotIn("hidden", etiqueta)
        self.assertNotIn("data-mensajes-id", etiqueta)
        self.assertEqual(html.count(f'id="galeria-{self.producto.pk}"'), 1)
        # El aviso de cambios tiene SU id: nunca el del bloque, o al ocultarlo
        # se llevaría por delante la galería entera.
        self.assertIn(f'data-aviso-id="galeria-cambios-{self.producto.pk}"', etiqueta)
        self.assertNotEqual(f"galeria-cambios-{self.producto.pk}", f"galeria-{self.producto.pk}")

    def test_el_bloque_carga_su_script_solo_en_productos(self):
        respuesta = self.client.get(self.url_editar)
        self.assertContains(respuesta, "js/modulos/productos/galeria/carga.js")

        colecciones = self.client.get(
            reverse("core:admin_section", kwargs={"seccion": "colecciones"})
        )
        self.assertNotContains(colecciones, "js/modulos/productos/galeria/carga.js")


class SinJavaScriptTests(_BasePantalla):
    """Todo lo esencial se hace sin JavaScript: el servidor no depende de él."""

    def test_las_posiciones_tambien_se_pueden_escribir_en_el_panel(self):
        galeria.agregar_archivos(self.producto, fotos(2))
        primera, segunda = self.filas()
        respuesta = self.client.get(
            reverse("core:admin_section", kwargs={"seccion": "productos"})
        )

        for lugar, fila in enumerate((primera, segunda), start=1):
            self.assertContains(
                respuesta,
                f'type="number" name="posicion-{fila.pk}" value="{lugar}" data-posicion-campo',
                count=1,
            )
        self.assertContains(respuesta, "Escribe la posición de cada foto para cambiar el orden.")

    def test_sin_javascript_se_puede_subir_reordenar_y_eliminar(self):
        html = self.client.get(self.url_editar).content.decode()
        # El formulario de subida es un POST completo, sin depender de scripts.
        self.assertIn('enctype="multipart/form-data"', html)
        self.assertIn('name="accion" value="subir"', html)

        creadas = self.enviar("subir", fotografias=[foto(), foto()])
        self.assertEqual(creadas.status_code, 302)
        primera, segunda = self.filas()

        # Con fotos guardadas, el formulario de orden también es un POST normal.
        html = self.client.get(self.url_editar).content.decode()
        self.assertIn('name="accion" value="organizar"', html)

        # Lo que enviarían los botones «bajar» de la primera: posiciones 2 y 1.
        respuesta = self.enviar(
            "organizar",
            **{f"posicion-{primera.pk}": 2, f"posicion-{segunda.pk}": 1, "principal": segunda.pk},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self.ids(), [segunda.pk, primera.pk])
        self.assertEqual(self.principal(), segunda.pk)

        self.enviar("eliminar", imagen=segunda.pk)
        self.assertEqual(self.ids(), [primera.pk])

    def test_el_servidor_sigue_rechazando_lo_que_el_navegador_avisa(self):
        excesivo = self.enviar(
            "subir", fotografias=[archivo_que_no_es_imagen("anillo.gif")]
        )

        self.assertRedirects(excesivo, f"{self.url_editar}#galeria", fetch_redirect_response=False)
        self.assertEqual(cuantas_fotos(self.producto), 0)

    def test_el_servidor_sigue_rechazando_pasarse_del_maximo(self):
        galeria.agregar_archivos(self.producto, fotos(MAX_IMAGENES_POR_PRODUCTO))
        antes = cuantas_fotos(self.producto)

        respuesta = self.enviar("subir", fotografias=[foto()])

        self.assertRedirects(respuesta, f"{self.url_editar}#galeria", fetch_redirect_response=False)
        self.assertEqual(cuantas_fotos(self.producto), antes)


def archivo_gif():
    """Un GIF válido (formato no permitido), con el tipo MIME que diría Windows."""
    from io import BytesIO

    from PIL import Image

    memoria = BytesIO()
    Image.new("P", (8, 8)).save(memoria, format="GIF")
    return SimpleUploadedFile("anillo.gif", memoria.getvalue(), content_type="image/gif")


def cuantas_fotos(producto):
    return len(galeria.listar(producto))
