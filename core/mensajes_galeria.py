"""Textos de la galería: los mismos en el servidor y en la pantalla.

El navegador valida antes de enviar (velocidad y comodidad) y el servidor valida
siempre (seguridad). Para que nadie vea dos mensajes distintos del mismo
problema, los textos viven aquí una sola vez:

- `core/imagenes.py` los usa al rechazar un archivo.
- `core/servicio_galeria.py` los usa al rechazar un envío o pasarse del máximo.
- `core/vistas_galeria.py` los publica en el HTML y
  `static/js/modulos/productos/galeria/carga.js` los repite en el navegador.

Si cambia un límite, cambia aquí y las tres capas dicen lo mismo. Los textos se
escriben en español, sin datos dinámicos: cuando hace falta un número, la
función lo recibe.

Este módulo no importa Django ni nada del proyecto: solo cadenas y funciones
puras, para poder leerlo desde cualquier capa sin crear dependencias.
"""

# Qué significa un error (código) y qué se le dice a la persona.
# Los códigos coinciden con los de `ValidationError` en `core/imagenes.py`, salvo
# `limite_navegador` y `duplicada`, que solo existen en la pantalla: el servidor
# nunca recibe dos veces el mismo archivo ni necesita saber cuántos huecos hay.
MENSAJES = {
    "formato": (
        "El formato {formato} no está permitido. Usa un archivo JPG, PNG o WebP."
    ),
    "no_imagen": (
        "No pudimos reconocer el archivo como una imagen. Usa un archivo JPG, PNG o WebP."
    ),
    "vacio": "El archivo está vacío. Selecciona otra imagen.",
    "pesada": (
        "La imagen pesa más de {mb_por_imagen} MB. "
        "Reduce su tamaño y vuelve a intentarlo."
    ),
    "envio_pesado": (
        "Las imágenes seleccionadas pesan más de {mb_por_envio} MB en total. "
        "Envía menos fotografías a la vez."
    ),
    "limite": (
        "Una galería admite como máximo {maximo} fotografías. "
        "Este producto ya tiene {actuales} y quieres añadir {nuevas}."
    ),
    "limite_navegador": (
        "Has alcanzado el límite de {maximo} fotografías. "
        "Quita una de las seleccionadas para añadir otra."
    ),
    "dimensiones": (
        "La imagen {medida}supera el máximo permitido: {lado} px por lado "
        "y {megapixeles} megapíxeles."
    ),
    "animada": (
        "Las imágenes animadas no están permitidas. Usa una fotografía fija."
    ),
    "danada": (
        "La imagen está dañada o incompleta. Vuelve a exportarla e inténtalo de nuevo."
    ),
    "duplicada": "«{nombre}» ya está en la lista: no se añadió dos veces.",
    "sin_archivos": "Selecciona al menos una fotografía de tu equipo.",
}

# Descripción corta de un archivo para anteponer a su error: «anillo.jpg»: …
ETIQUETA_ARCHIVO = "«{nombre}»: {mensaje}"


def mensaje(codigo, **datos):
    """Texto para una persona, a partir del código del error y sus datos."""
    return MENSAJES[codigo].format(**datos)


def texto_dimensiones(ancho, alto, lado, megapixeles):
    """Frase de dimensiones; sin medidas cuando el archivo no llegó a abrirse."""
    medida = f"mide {ancho}×{alto} px y " if ancho else ""
    return mensaje(
        "dimensiones", medida=medida, lado=lado, megapixeles=megapixeles
    )


def error_de_archivo(nombre, mensaje_del_error):
    """Cómo se nombra el problema de un archivo concreto en un envío."""
    return ETIQUETA_ARCHIVO.format(nombre=nombre, mensaje=mensaje_del_error)
