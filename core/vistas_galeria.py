"""Pantalla de la galería de un producto (Paso 03c).

Este módulo solo traduce lo que llega del navegador en llamadas a
`core.servicio_galeria`. No valida imágenes ni conoce las reglas de la galería
(máximo, principal, orden): todo eso vive en el servicio y en `core.imagenes`.

Lo que sí decide esta capa, porque es cosa de la pantalla:
- Quién puede entrar: personal con el permiso `core.change_producto`.
- Un producto publicado no puede quedarse sin su única fotografía (Paso 03d).
- Las posiciones se muestran como 1, 2, 3...; el servicio trabaja con 0, 1, 2...
- Al servicio solo se le envían las fotografías cuyo número cambió, que es
  como `reordenar` sabe cuál se movió a propósito.
- A dónde volver después de cada acción (`siguiente`), sin salir del sitio.

El bloque se pinta con `templates/core/productos/_galeria.html` y se usa en
dos pantallas: la ficha del producto en el panel y el formulario de edición.
"""

import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import servicio_galeria
from .imagenes import (
    FORMATOS_POR_EXTENSION,
    MAX_ANCHO_VISTA_PREVIA,
    MAX_BYTES_POR_ENVIO,
    MAX_BYTES_POR_IMAGEN,
    MAX_LADO_PX,
    MAX_PIXELES,
    MB,
)
from .mensajes_galeria import ETIQUETA_ARCHIVO, MENSAJES, mensaje
from .models import Producto

logger = logging.getLogger(__name__)

# Lo que el selector de archivos del navegador ofrece por defecto. Es solo una
# ayuda: lo que de verdad se acepta lo decide `core.imagenes` por el contenido.
TIPOS_SUGERIDOS = "image/jpeg,image/png,image/webp"


MENSAJE_ULTIMA_FOTOGRAFIA = (
    "Este producto está publicado y esta es su única fotografía. "
    "Sube otra antes de eliminarla o guarda el producto como borrador."
)


def etiqueta_de_mensajes(producto_id):
    """Marca los mensajes de una galería para pintarlos dentro de su bloque.

    El mismo valor numera los dos avisos que lleva el bloque: el de la última
    acción (mensajes de Django) y el de «cambios sin guardar», que escribe
    `static/js/modulos/productos/galeria/carga.js`.
    """
    return f"galeria-{producto_id}"


def contexto_galeria(producto, imagenes, siguiente=""):
    """Datos que necesita `core/productos/_galeria.html` para un producto."""
    imagenes = list(imagenes)
    maximo = servicio_galeria.MAX_IMAGENES_POR_PRODUCTO
    return {
        "producto": producto,
        "imagenes": imagenes,
        "total": len(imagenes),
        "maximo": maximo,
        "libres": max(maximo - len(imagenes), 0),
        "url_accion": reverse("core:producto_galeria", args=[producto.pk]),
        "siguiente": siguiente,
        "etiqueta": etiqueta_de_mensajes(producto.pk),
        "tipos_sugeridos": TIPOS_SUGERIDOS,
        "mb_por_imagen": MAX_BYTES_POR_IMAGEN // MB,
        "mb_por_envio": MAX_BYTES_POR_ENVIO // MB,
        "largo_maximo_url": servicio_galeria.LARGO_MAXIMO_URL,
        # Paso 03d: qué muestra hoy la tienda y qué falta para publicar.
        "gestionada": producto.galeria_gestionada,
        "usa_url_antigua": not producto.galeria_gestionada and bool(producto.imagen_url),
        # Lo que necesita el navegador para validar antes de enviar. Son los
        # mismos números y los mismos textos que usa el servidor: ver
        # `configuracion_para_el_navegador`.
        "configuracion": configuracion_para_el_navegador(imagenes),
        # Id del <script type="application/json"> que lee `carga.js`. Lleva el
        # producto porque el panel pinta una galería por fila.
        "configuracion_id": f"galeria-config-{producto.pk}",
    }


def configuracion_para_el_navegador(imagenes):
    """Límites y mensajes que `carga.js` repite en el navegador.

    No sustituye a la validación del servidor, que sigue siendo la única que
    decide: aquí solo se evita un viaje inútil al servidor y se avisa antes.
    Los mensajes salen de `core.mensajes_galeria`, los mismos que el servidor.
    """
    return {
        "maximo": servicio_galeria.MAX_IMAGENES_POR_PRODUCTO,
        "libres": max(servicio_galeria.MAX_IMAGENES_POR_PRODUCTO - len(imagenes), 0),
        "maximoPorImagen": MAX_BYTES_POR_IMAGEN,
        "maximoPorEnvio": MAX_BYTES_POR_ENVIO,
        "mbPorImagen": MAX_BYTES_POR_IMAGEN // MB,
        "mbPorEnvio": MAX_BYTES_POR_ENVIO // MB,
        "ladoMaximo": MAX_LADO_PX,
        "megapixelesMaximos": MAX_PIXELES // 1_000_000,
        "anchoVistaPrevia": MAX_ANCHO_VISTA_PREVIA,
        "tipos": sorted(FORMATOS_POR_EXTENSION),
        "mensajes": MENSAJES,
        "etiquetaArchivo": ETIQUETA_ARCHIVO,
    }


# ---------------------------------------------------------------------------
# Acciones: cada una devuelve el mensaje de éxito o lanza ValidationError.
# ---------------------------------------------------------------------------


def _subir(request, producto):
    archivos = request.FILES.getlist("fotografias")
    if not archivos:
        raise ValidationError(mensaje("sin_archivos"), code="sin_archivos")
    creadas = servicio_galeria.agregar_archivos(producto, archivos)
    if len(creadas) == 1:
        return "Se añadió 1 fotografía."
    return f"Se añadieron {len(creadas)} fotografías."


def _agregar_url(request, producto):
    servicio_galeria.agregar_url(producto, request.POST.get("url", ""))
    return "Se añadió la fotografía por dirección web."


def _posicion(valor, total):
    """Posición escrita en la pantalla (1, 2, 3...) → posición del servicio (0, 1, 2...).

    Un número mayor que la galería equivale a «al final».
    """
    try:
        numero = int(str(valor).strip())
    except ValueError as exc:
        raise ValidationError("La posición debe ser un número entero.", code="orden") from exc
    if numero < 1:
        raise ValidationError(f"La posición debe estar entre 1 y {total}.", code="orden")
    return min(numero, total) - 1


def _organizar(request, producto):
    """Guarda en un solo envío la fotografía principal y las posiciones.

    La pantalla no pinta un número por fotografía (son diez campos de texto para
    hacer el mismo trabajo): manda `posicion-<pk>` calculado por sus botones
    «subir» y «bajar», con los mismos valores 1..N que espera el servicio. Aquí
    no cambia nada: si un valor falta, esa fotografía se queda donde está.
    """
    imagenes = servicio_galeria.listar(producto)
    movidas = {}
    for lugar, imagen in enumerate(imagenes):
        valor = request.POST.get(f"posicion-{imagen.pk}")
        if valor is None:
            continue
        posicion = _posicion(valor, len(imagenes))
        if posicion != lugar:
            movidas[imagen.pk] = posicion

    elegida = request.POST.get("principal")
    actual = next((str(imagen.pk) for imagen in imagenes if imagen.es_principal), None)
    cambia_principal = bool(elegida) and elegida != actual
    if not movidas and not cambia_principal:
        return "No había cambios que guardar en la galería."

    # Las dos cosas juntas o ninguna: si el orden falla, la principal no cambia.
    with transaction.atomic():
        if cambia_principal:
            servicio_galeria.establecer_principal(producto, elegida)
        if movidas:
            servicio_galeria.reordenar(producto, movidas)
    return "Se guardaron el orden y la fotografía principal."


def _eliminar(request, producto):
    """Elimina una fotografía, salvo que deje sin imagen a un producto publicado.

    El servicio no decide sobre la publicación (ver su docstring); esa regla es
    del Paso 03d y se comprueba aquí, con el producto bloqueado para que dos
    personas no puedan borrar a la vez las dos últimas fotografías.
    """
    imagen_id = request.POST.get("imagen")
    with transaction.atomic():
        vigente = Producto.objects.select_for_update().get(pk=producto.pk)
        if vigente.es_publico:
            ids = list(vigente.imagenes.values_list("pk", flat=True)[:2])
            if len(ids) == 1 and str(ids[0]) == str(imagen_id).strip():
                raise ValidationError(MENSAJE_ULTIMA_FOTOGRAFIA, code="publicado")
        servicio_galeria.eliminar_imagen(vigente, imagen_id)
    return "Se eliminó la fotografía."


ACCIONES = {
    "subir": _subir,
    "url": _agregar_url,
    "organizar": _organizar,
    "eliminar": _eliminar,
}


def _destino(request, producto):
    """A dónde volver: la dirección pedida si es de este sitio; si no, la ficha."""
    siguiente = request.POST.get("siguiente", "")
    if siguiente and url_has_allowed_host_and_scheme(
        siguiente,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return siguiente
    return reverse("core:producto_editar", args=[producto.pk]) + "#galeria"


# El orden de los decoradores es el mismo que en `producto_guardar`: primero se
# comprueba quién es el usuario y solo después el método HTTP.
@staff_member_required
@require_POST
def producto_galeria(request, pk):
    """Ejecuta una acción de la galería y vuelve a la pantalla de origen."""
    if not request.user.has_perm("core.change_producto"):
        raise PermissionDenied
    producto = get_object_or_404(Producto, pk=pk)
    accion = ACCIONES.get(request.POST.get("accion"))
    if accion is None:
        raise PermissionDenied("La acción solicitada no está disponible.")

    etiqueta = etiqueta_de_mensajes(producto.pk)
    try:
        mensaje = accion(request, producto)
    except ValidationError as error:
        for texto in error.messages:
            messages.error(request, texto, extra_tags=etiqueta)
    except OSError:
        # El servicio ya deshizo lo que había escrito; aquí solo se avisa.
        logger.exception("Fallo de almacenamiento en la galería del producto %s.", producto.pk)
        messages.error(
            request,
            "No se pudieron guardar los archivos. No se cambió nada; inténtalo de nuevo.",
            extra_tags=etiqueta,
        )
    else:
        messages.success(request, mensaje, extra_tags=etiqueta)
    return redirect(_destino(request, producto))
