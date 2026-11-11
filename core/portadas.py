"""Portada de una colección (Paso 04): el archivo que se sube desde el panel.

Tres piezas, en este orden:

- `CampoPortada` (formulario): pasa el archivo subido por `core.imagenes` —los
  mismos límites y la misma limpieza que las fotografías de producto; aquí no
  se repite ninguna regla— y entrega la versión que se guarda.
- `cuidar_archivo`: rodea a `Coleccion.save()` para que el disco y la base de
  datos no se separen cuando algo falla o cuando la portada cambia.
- `borrar_si_nadie_la_usa`: borra un archivo de portada que ya no usa ninguna
  colección (también lo llama `core/signals.py` al eliminar una colección).

Qué se guarda. `Coleccion` tiene UN solo campo de archivo, así que se guarda UNA
versión: la de «detalle» (WebP, lado mayor de hasta 1200 px), que es la que
enseña la tienda. El original no se conserva. Si algún día hace falta, se cambia
en `CampoPortada.to_python` y pide otro campo en el modelo (una migración).

Garantías:
- Un archivo solo se borra si tiene la forma `colecciones/<archivo>` y, además,
  ninguna colección lo usa en ese momento.
- El archivo anterior se borra cuando la transacción YA se confirmó: si se
  revierte, sigue en su sitio.
- Si el guardado falla después de escribir el archivo nuevo, ese archivo se borra.

Límites conocidos (los mismos del servicio de galería):
- Django no avisa cuando una transacción se revierte. Si quien guarda lo hace
  dentro de una transacción propia y esta se revierte DESPUÉS de un guardado
  correcto, el archivo nuevo queda en el disco sin colección que lo use.
- Si el almacenamiento falla a mitad de escribir, puede quedar un archivo
  incompleto cuyo nombre no llega a conocerse.
- `QuerySet.update()` y `bulk_update()` no pasan por `Coleccion.save()`: si se
  cambia la portada por esa vía, el archivo anterior no se borra.

Este módulo NO importa `core.models`: es `models.py` quien lo importa a él.
"""

import logging
import re
from contextlib import contextmanager

from django import forms
from django.core.files.base import ContentFile
from django.db import DatabaseError, connections, transaction
from django.forms.utils import flatatt
from django.utils.html import format_html

from .imagenes import MAX_BYTES_POR_IMAGEN, MB, procesar_imagen

logger = logging.getLogger(__name__)

CAMPO = "imagen"
# Contrato con `core.upload_paths.ruta_imagen_coleccion`: `colecciones/<uuid>.<ext>`.
# Del disco solo se borra lo que tenga exactamente esa forma.
_RUTA_DE_PORTADA = re.compile(r"colecciones/[A-Za-z0-9_-]+\.[A-Za-z0-9]+")

# Solo orienta al elegir el archivo: lo que decide es su contenido real.
TIPOS_ACEPTADOS = "image/jpeg,image/png,image/webp"
# De este nombre solo se usa la extensión: en el disco el archivo se llama con un UUID.
NOMBRE_AL_GUARDAR = "portada.webp"
ANCHO_VISTA_PREVIA = 96

AYUDA_PORTADA = (
    f"JPG, PNG o WebP de hasta {MAX_BYTES_POR_IMAGEN // MB} MB. "
    "Se guarda una versión optimizada, no el original. "
    "La tienda la muestra en vertical (3:4) y recorta lo que sobra."
)


# ---------------------------------------------------------------------------
# Formulario
# ---------------------------------------------------------------------------

class SelectorDePortada(forms.ClearableFileInput):
    """Selector de archivo que enseña la portada guardada y permite quitarla.

    Arma su HTML aquí mismo en lugar de usar una plantilla: los formularios del
    proyecto se pintan con `{{ field }}` en pantallas distintas (el panel y el
    formulario de colecciones) y así sale igual en todas.
    """

    clear_checkbox_label = "Quitar la portada actual"

    def render(self, name, value, attrs=None, renderer=None):
        datos = self.get_context(name, value, attrs)["widget"]
        atributos = dict(datos["attrs"])
        marcada = bool(atributos.pop("checked", False))
        selector = format_html('<input type="file" name="{}"{}>', name, flatatt(atributos))
        if not datos["is_initial"]:
            return selector

        casilla = ""
        if not self.is_required:
            casilla = format_html(
                '<label class="portada-campo__quitar" for="{}"><input{}> {}</label>',
                datos["checkbox_id"],
                flatatt(
                    {
                        "type": "checkbox",
                        "name": datos["checkbox_name"],
                        "id": datos["checkbox_id"],
                        "checked": marcada,
                        "disabled": bool(atributos.get("disabled")),
                    }
                ),
                self.clear_checkbox_label,
            )
        return format_html(
            '<div class="portada-campo">'
            '<span class="portada-campo__actual">'
            '<img src="{}" alt="" width="{}" loading="lazy">'
            "<span>Portada actual</span>"
            "</span>{}{}</div>",
            datos["value"].url,
            ANCHO_VISTA_PREVIA,
            selector,
            casilla,
        )


class CampoPortada(forms.FileField):
    """Campo de formulario de la portada: valida, limpia y optimiza la imagen.

    Lo que devuelve —y por tanto lo que el modelo guarda— NO es el archivo que
    subió la persona, sino la versión ya procesada por `core.imagenes`.
    """

    widget = SelectorDePortada
    default_error_messages = {
        "invalid": "No se recibió el archivo. Elige la imagen otra vez e inténtalo de nuevo.",
        "missing": "No se recibió ningún archivo.",
        "contradiction": (
            "Elige una sola cosa: subir una fotografía nueva o quitar la portada actual."
        ),
    }

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("label", "Portada (archivo)")
        kwargs.setdefault("help_text", AYUDA_PORTADA)
        # Un archivo vacío llega hasta `core.imagenes`, que lo rechaza con su mensaje.
        super().__init__(allow_empty_file=True, **kwargs)
        self.widget.attrs.setdefault("accept", TIPOS_ACEPTADOS)

    def to_python(self, data):
        # pylint-django toma este campo por un archivo y no ve el método heredado.
        archivo = super().to_python(data)  # pylint: disable=no-member
        if archivo is None:
            return None
        resultado = procesar_imagen(archivo)  # lanza ValidationError con el motivo
        return ContentFile(resultado.detalle, name=NOMBRE_AL_GUARDAR)


# ---------------------------------------------------------------------------
# Archivos en el disco
# ---------------------------------------------------------------------------

def _nombre(coleccion):
    """Nombre del archivo de portada que lleva el objeto en memoria ("" si no tiene)."""
    return getattr(coleccion, CAMPO).name or ""


def _nombre_guardado(coleccion):
    """Nombre del archivo que la base de datos tiene AHORA para esa colección."""
    if coleccion.pk is None:
        return ""
    guardado = type(coleccion).objects.filter(pk=coleccion.pk).values_list(CAMPO, flat=True)
    return guardado.first() or ""


def _borrar(modelo, nombre):
    """Borra el archivo del almacenamiento; devuelve True si lo borró.

    Un fallo del disco (`OSError`) se anota en el registro y no se propaga.
    """
    if not _RUTA_DE_PORTADA.fullmatch(str(nombre or "")):
        logger.warning("No se borra %r: no es un archivo de portada.", nombre)
        return False
    try:
        modelo._meta.get_field(CAMPO).storage.delete(nombre)
    except OSError:
        logger.exception("No se pudo borrar la portada %r.", nombre)
        return False
    return True


def borrar_si_nadie_la_usa(modelo, nombre):
    """Borra un archivo de portada que ya no usa ninguna colección.

    Devuelve True si lo borró. Un fallo del disco o de la base de datos se anota
    en el registro y no se propaga. La comprobación se hace justo antes de
    borrar, así que debe llamarse con la transacción ya confirmada.
    """
    try:
        en_uso = modelo.objects.filter(**{CAMPO: nombre}).exists()
    except DatabaseError:
        logger.exception("No se pudo comprobar si la portada %r sigue en uso.", nombre)
        return False
    if en_uso:
        return False
    return _borrar(modelo, nombre)


def programar_borrado(modelo, nombre):
    """Al confirmarse la transacción, borra `nombre` si ninguna colección lo usa.

    Sin transacción abierta se ejecuta en el momento. Si la transacción se
    revierte, no se ejecuta: el archivo sigue en su sitio.
    """
    if nombre:
        transaction.on_commit(lambda: borrar_si_nadie_la_usa(modelo, nombre))


def _transaccion_condenada(modelo):
    """True dentro de una transacción que, tras un error, ya solo puede revertirse.

    En ese estado Django no deja consultar la base de datos; tampoco hace falta:
    nada de lo escrito en esa transacción va a quedar.
    """
    conexion = connections[modelo.objects.db]
    return conexion.in_atomic_block and conexion.needs_rollback


def _descartar_recien_escrito(modelo, nombre):
    """Borra el archivo que un guardado fallido alcanzó a escribir."""
    if _transaccion_condenada(modelo):
        return _borrar(modelo, nombre)
    # Fuera de una transacción (o si el fallo llegó después de escribir la fila)
    # se comprueba primero: si la fila sí quedó guardada, el archivo es suyo.
    return borrar_si_nadie_la_usa(modelo, nombre)


@contextmanager
def cuidar_archivo(coleccion):
    """Rodea a `Coleccion.save()`: el disco y la base de datos no deben separarse.

    - Si el guardado falla después de escribir el archivo nuevo, ese archivo se
      borra (no queda huérfano) y el objeto vuelve a apuntar a la portada que
      tiene en la base de datos, para que un reintento no guarde una ruta rota.
    - Si el guardado sale bien y la portada cambió (otra fotografía, o ninguna),
      el archivo anterior se borra al confirmarse la transacción, y solo si
      ninguna colección lo sigue usando.
    """
    modelo = type(coleccion)
    anterior = _nombre_guardado(coleccion)
    al_empezar = _nombre(coleccion)
    try:
        yield
    except Exception:
        escrito = _nombre(coleccion)
        # El nombre solo cambia durante el guardado cuando se escribe un archivo.
        if escrito and escrito != al_empezar and _descartar_recien_escrito(modelo, escrito):
            setattr(coleccion, CAMPO, anterior)
        raise
    if anterior and anterior != _nombre(coleccion):
        programar_borrado(modelo, anterior)
