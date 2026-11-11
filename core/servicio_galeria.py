"""Servicio de galería de imágenes de un producto (Paso 03b).

Aquí viven TODAS las reglas de la galería. Las pantallas (dashboard) y,
más adelante, cualquier otra vía deben pasar por este módulo en lugar de
tocar `ProductoImagen` directamente; así las reglas se escriben una sola vez.

Reglas que este servicio garantiza (la base de datos solo garantiza «una sola
fuente por fila» y «a lo sumo una principal»):

- Máximo `MAX_IMAGENES_POR_PRODUCTO` fotografías por producto (archivos y URL
  cuentan por igual).
- Si hay fotografías, hay EXACTAMENTE UNA principal.
- `orden` siempre queda consecutivo desde 0 (0, 1, 2, ...), sin huecos.
- Cada operación es todo o nada: si algo falla, no queda ninguna fila a medias
  ni archivos huérfanos en el disco.
- Una fotografía solo se puede tocar a través del producto al que pertenece
  (se busca siempre dentro de `producto.imagenes`), de modo que un identificador
  de otro producto —o inventado— se rechaza.
- Al borrar una fotografía se borran sus tres archivos (original y derivados),
  pero solo si están dentro de la carpeta del propio producto.

Lo que este servicio NO hace (es responsabilidad de quien lo llama):
- Comprobar permisos: la vista debe exigir `core.change_producto` antes.
- Decidir qué se muestra en la tienda ni cuándo un producto puede publicarse
  (eso es el Paso 03d).

La posición de una fotografía y cuál es la principal son cosas independientes:
cambiar la principal no mueve la fotografía de lugar.
"""

import logging
from collections.abc import Mapping

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import URLValidator
from django.db import transaction

from .imagenes import procesar_imagen, validar_envio
from .models import Producto, ProductoImagen

logger = logging.getLogger(__name__)

MAX_IMAGENES_POR_PRODUCTO = 5
MAX_POSICION = 32767  # tope de PositiveSmallIntegerField en todas las bases de datos
LARGO_MAXIMO_URL = ProductoImagen._meta.get_field("url").max_length
_VALIDADOR_URL = URLValidator(schemes=["http", "https"])


MENSAJE_NO_PERTENECE = "La fotografía indicada no pertenece a este producto."


def _error(mensaje, codigo):
    return ValidationError(mensaje, code=codigo)


def _mensaje_limite(actuales, nuevas):
    return (
        f"Una galería admite como máximo {MAX_IMAGENES_POR_PRODUCTO} fotografías. "
        f"Este producto ya tiene {actuales} y quieres añadir {nuevas}."
    )


def _producto_bloqueado(producto):
    """Fila del producto bloqueada hasta el final de la transacción.

    Dos administradores que editan la misma galería a la vez quedan en fila, así
    que ninguno ve un conteo desactualizado. (SQLite ignora el bloqueo, pero
    serializa las escrituras de todos modos.)
    """
    return Producto.objects.select_for_update().get(pk=producto.pk)


def _imagenes(producto):
    return list(ProductoImagen.objects.filter(producto_id=producto.pk))  # ya ordenadas


def _obtener(producto, imagen_id):
    """La fotografía, buscada SIEMPRE dentro del producto indicado."""
    try:
        return ProductoImagen.objects.get(pk=imagen_id, producto_id=producto.pk)
    except (ProductoImagen.DoesNotExist, ValueError, TypeError) as exc:
        raise _error(MENSAJE_NO_PERTENECE, "no_pertenece") from exc


def _normalizar(producto):
    """Deja la galería consistente: orden 0..n-1 y exactamente una principal."""
    imagenes = _imagenes(producto)
    cambiadas = []
    for posicion, imagen in enumerate(imagenes):
        if imagen.orden != posicion:
            imagen.orden = posicion
            cambiadas.append(imagen)
    if cambiadas:
        ProductoImagen.objects.bulk_update(cambiadas, ["orden"])
    if imagenes and not any(imagen.es_principal for imagen in imagenes):
        primera = imagenes[0]
        ProductoImagen.objects.filter(pk=primera.pk).update(es_principal=True)
        primera.es_principal = True
    return imagenes


def _marcar_gestionada(producto):
    """La galería pasa a ser la fuente de verdad del producto (Decisión 6)."""
    if not producto.galeria_gestionada:
        Producto.objects.filter(pk=producto.pk).update(galeria_gestionada=True)
        producto.galeria_gestionada = True


def _nombres_de_archivos(imagen):
    return [
        campo.name
        for campo in (imagen.archivo, imagen.archivo_detalle, imagen.archivo_miniatura)
        if campo
    ]


def _borrar_archivos(producto_id, nombres, almacenamiento):
    """Borra del disco solo lo que está en la carpeta del producto."""
    carpeta = f"productos/{producto_id}/"
    for nombre in nombres:
        if not nombre.startswith(carpeta) or ".." in nombre:
            logger.warning("No se borra %r: está fuera de %r.", nombre, carpeta)
            continue
        try:
            almacenamiento.delete(nombre)
        except OSError:
            logger.exception("No se pudo borrar el archivo %r.", nombre)


def _procesar_todas(archivos):
    """Procesa cada archivo ANTES de escribir nada: o valen todos o no entra ninguno."""
    procesadas = []
    for archivo in archivos:
        try:
            procesadas.append(procesar_imagen(archivo))
        except ValidationError as exc:
            nombre = str(getattr(archivo, "name", "") or "archivo")[:60]
            raise ValidationError(
                [f"«{nombre}»: {mensaje}" for mensaje in exc.messages], code=exc.code
            ) from exc
    return procesadas


def _guardar_archivos(imagen, resultado, guardados):
    """Escribe los tres archivos de una fotografía y apunta cada ruta en `guardados`."""
    destinos = (
        (imagen.archivo, f"original{resultado.extension_original}", resultado.original),
        (imagen.archivo_detalle, "detalle.webp", resultado.detalle),
        (imagen.archivo_miniatura, "miniatura.webp", resultado.miniatura),
    )
    for campo, nombre, contenido in destinos:
        campo.save(nombre, ContentFile(contenido), save=False)
        guardados.append(campo.name)


def listar(producto):
    """Fotografías del producto, en el orden en que deben mostrarse."""
    return _imagenes(producto)


def principal(producto):
    """La fotografía principal, o None si el producto no tiene galería."""
    return ProductoImagen.objects.filter(producto_id=producto.pk, es_principal=True).first()


def agregar_archivos(producto, archivos):
    """Añade fotografías subidas desde el equipo. Devuelve las filas creadas.

    Todo o nada: si una sola fotografía no es válida, o se pasa del máximo, no se
    guarda ninguna. La primera fotografía de una galería vacía queda como
    principal; las demás se añaden al final.
    """
    archivos = list(archivos)
    if not archivos:
        return []
    validar_envio(archivos)
    existentes = ProductoImagen.objects.filter(producto_id=producto.pk).count()
    if existentes + len(archivos) > MAX_IMAGENES_POR_PRODUCTO:
        raise _error(_mensaje_limite(existentes, len(archivos)), "limite")
    procesadas = _procesar_todas(archivos)  # lo pesado, fuera del bloqueo

    guardados = []
    almacenamiento = ProductoImagen._meta.get_field("archivo").storage
    try:
        with transaction.atomic():
            bloqueado = _producto_bloqueado(producto)
            actuales = _imagenes(bloqueado)
            if len(actuales) + len(procesadas) > MAX_IMAGENES_POR_PRODUCTO:
                raise _error(_mensaje_limite(len(actuales), len(procesadas)), "limite")
            hay_principal = any(imagen.es_principal for imagen in actuales)
            creadas = []
            for posicion, resultado in enumerate(procesadas):
                imagen = ProductoImagen(
                    producto=bloqueado,
                    orden=len(actuales) + posicion,
                    es_principal=not hay_principal and posicion == 0,
                )
                _guardar_archivos(imagen, resultado, guardados)
                imagen.full_clean()
                imagen.save()
                creadas.append(imagen)
            _marcar_gestionada(bloqueado)
    except Exception:
        _borrar_archivos(producto.pk, guardados, almacenamiento)
        raise
    producto.galeria_gestionada = True
    return creadas


def agregar_url(producto, url):
    """Añade una fotografía externa por URL (solo http/https; nunca se descarga)."""
    url = (url or "").strip()
    if not url or len(url) > LARGO_MAXIMO_URL:
        raise _error(
            f"Indica una dirección de hasta {LARGO_MAXIMO_URL} caracteres.", "url_invalida"
        )
    try:
        _VALIDADOR_URL(url)
    except ValidationError as exc:
        raise _error(
            "La dirección debe empezar por http:// o https:// y ser una URL válida.",
            "url_invalida",
        ) from exc

    with transaction.atomic():
        bloqueado = _producto_bloqueado(producto)
        actuales = _imagenes(bloqueado)
        if len(actuales) + 1 > MAX_IMAGENES_POR_PRODUCTO:
            raise _error(_mensaje_limite(len(actuales), 1), "limite")
        imagen = ProductoImagen(
            producto=bloqueado,
            url=url,
            orden=len(actuales),
            es_principal=not any(i.es_principal for i in actuales),
        )
        imagen.full_clean()
        imagen.save()
        _marcar_gestionada(bloqueado)
    producto.galeria_gestionada = True
    return imagen


def establecer_principal(producto, imagen_id):
    """Convierte una fotografía en la principal (la anterior deja de serlo)."""
    with transaction.atomic():
        bloqueado = _producto_bloqueado(producto)
        imagen = _obtener(bloqueado, imagen_id)
        # Primero se quita y después se pone: la restricción «una sola principal»
        # nunca llega a verse violada a mitad de la operación.
        ProductoImagen.objects.filter(producto_id=bloqueado.pk, es_principal=True).exclude(
            pk=imagen.pk
        ).update(es_principal=False)
        ProductoImagen.objects.filter(pk=imagen.pk).update(es_principal=True)
    imagen.es_principal = True
    return imagen


def reordenar(producto, posiciones):
    """Aplica posiciones numéricas {id_de_fotografia: posicion} y las normaliza.

    La interfaz envía un número por fotografía; aquí se convierten en 0, 1, 2...
    Los empates se resuelven por el orden que ya tenían. Las fotografías que no
    se mencionen conservan su posición actual. Si un número no es válido, o un
    identificador no pertenece al producto, no se cambia nada.
    """
    if not isinstance(posiciones, Mapping):
        raise _error("Las posiciones deben indicarse como {fotografía: posición}.", "orden")
    pedidas = {}
    for imagen_id, valor in posiciones.items():
        try:
            if isinstance(valor, bool):
                raise ValueError
            numero = int(valor)
        except (TypeError, ValueError) as exc:
            raise _error("La posición debe ser un número entero.", "orden") from exc
        if not 0 <= numero <= MAX_POSICION:
            raise _error(f"La posición debe estar entre 0 y {MAX_POSICION}.", "orden")
        pedidas[imagen_id] = numero

    with transaction.atomic():
        bloqueado = _producto_bloqueado(producto)
        actuales = _imagenes(bloqueado)
        por_id = {str(imagen.pk): imagen for imagen in actuales}
        movidas = {}
        for imagen_id, numero in pedidas.items():
            imagen = por_id.get(str(imagen_id))
            if imagen is None:
                raise _error(MENSAJE_NO_PERTENECE, "no_pertenece")
            movidas[imagen.pk] = numero
        previo = {imagen.pk: imagen.orden for imagen in actuales}
        # A igual posición gana la fotografía que se movió a propósito («poner la C
        # en la posición 0» la deja primera); si ambas se movieron o ninguna, manda
        # el orden que ya tenían.
        actuales.sort(
            key=lambda imagen: (
                movidas.get(imagen.pk, previo[imagen.pk]),
                imagen.pk not in movidas,
                previo[imagen.pk],
            )
        )
        for posicion, imagen in enumerate(actuales):
            imagen.orden = posicion
        ProductoImagen.objects.bulk_update(actuales, ["orden"])


def eliminar_imagen(producto, imagen_id):
    """Elimina una fotografía y sus archivos; si era la principal, pasa la siguiente.

    Los archivos se borran del disco solo cuando la transacción ya se confirmó:
    si algo falla y se revierte, no se pierden las imágenes.
    """
    with transaction.atomic():
        bloqueado = _producto_bloqueado(producto)
        imagen = _obtener(bloqueado, imagen_id)
        nombres = _nombres_de_archivos(imagen)
        almacenamiento = imagen.archivo.storage
        imagen.delete()
        _normalizar(bloqueado)  # renumera y, si faltaba la principal, ascende a la primera
        transaction.on_commit(
            lambda: _borrar_archivos(bloqueado.pk, nombres, almacenamiento)
        )


def normalizar(producto):
    """Repara una galería inconsistente (orden con huecos o sin principal)."""
    with transaction.atomic():
        return _normalizar(_producto_bloqueado(producto))
