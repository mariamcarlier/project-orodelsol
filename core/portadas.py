"""Portada de una colección (Paso 04): el archivo que se sube desde el panel.

Tres piezas, en este orden:

- `CampoPortada` (formulario): pasa el archivo subido por `core.imagenes` —los
  mismos límites y la misma limpieza que las fotografías de producto; aquí no
  se repite ninguna regla— y entrega el original limpio junto con su versión
  optimizada.
- `cuidar_archivos`: rodea a `Coleccion.save()` para que el disco y la base de
  datos no se separen cuando algo falla o cuando la portada cambia, y para que
  la versión optimizada sea siempre la de la portada que queda guardada.
- `borrar_si_nadie_la_usa`: borra un archivo de portada que ya no usa ninguna
  colección (también lo usa `core/signals.py` al eliminar una colección).

Qué se guarda. Dos archivos por portada, igual que en `ProductoImagen`:

- `Coleccion.imagen` es el ORIGINAL limpio, tal como lo entrega
  `core.imagenes`: el mismo formato y las mismas medidas que el archivo subido,
  con su perfil de color, ya girado según su orientación y sin metadatos
  (ubicación, cámara). Para quitárselos se vuelve a codificar, así que no es
  idéntico byte a byte al archivo subido. Va en `colecciones/<uuid>.<ext>`.
  Optimizar nunca lo sustituye.
- `Coleccion.imagen_detalle` es la versión OPTIMIZADA que enseña la tienda:
  WebP, lado mayor de hasta 1200 px. Va en `colecciones/derivados/<uuid>.webp`
  y se puede volver a generar a partir del original.

`imagen_detalle` depende de `imagen`, y quien lo mantiene es `save()`:

- sin `imagen` no hay `imagen_detalle`;
- una `imagen` nueva que llega de `CampoPortada` trae su versión optimizada;
- si `imagen` cambia por otra vía (la consola, otro código) y nadie trae la
  versión optimizada, `imagen_detalle` se vacía y la tienda enseña `imagen`.

Una portada guardada cuando `imagen_detalle` aún no existía (antes de la
migración 0010) está en ese último caso: solo tiene `imagen`. Se sigue viendo y
sus archivos se limpian igual.

Garantías:
- Un archivo solo se borra si tiene una de las dos formas de arriba y, además,
  ninguna colección lo usa en ese momento (en ninguno de los dos campos).
- Los archivos anteriores se borran cuando la transacción YA se confirmó: si se
  revierte, siguen en su sitio.
- Si el guardado falla después de escribir los archivos nuevos, se borran, y
  el error que recibe quien guardó es el del guardado.
- Cada archivo se borra por separado: que uno no se deje borrar no impide
  borrar el otro, y ningún fallo al borrar llega a quien guardó; queda anotado
  en el registro.

Límites conocidos:
- Django no avisa cuando una transacción se revierte. Si quien guarda lo hace
  dentro de una transacción propia y esta se revierte DESPUÉS de un guardado
  correcto, los archivos nuevos quedan en el disco sin colección que los use.
- Si el almacenamiento falla a mitad de escribir, puede quedar un archivo
  incompleto cuyo nombre no llega a conocerse.
- Un archivo que no se pudo borrar se queda en el disco: no hay reintento
  automático. El registro dice cuál es.
- `QuerySet.update()` y `bulk_update()` no pasan por `Coleccion.save()`: si se
  cambia la portada por esa vía, los archivos anteriores no se borran y
  `imagen_detalle` no se actualiza. La portada se cambia SIEMPRE con `save()`
  (lo hacen `ColeccionForm`, el panel y el formulario de colecciones).
- Dos guardados de la misma colección en el mismo instante: si uno cambia la
  portada mientras el otro —que leyó la colección justo antes— guarda otros
  datos, el segundo vuelve a escribir la portada anterior (cuyos archivos ya se
  borraron) y borra la nueva. No hay bloqueo para ese caso.
- Si algo falla DESPUÉS de escribir la fila (hoy nada lo hace; lo haría un
  receptor de `post_save` que lance un error), la portada nueva queda guardada
  con sus archivos, pero los de la anterior no se borran.

Lo que hay que saber para operar el módulo está en `docs/galeria-imagenes.md`.

Este módulo NO importa `core.models`: es `models.py` quien lo importa a él.
"""

import logging
import re
from contextlib import contextmanager

from django import forms
from django.core.files.base import ContentFile
from django.db import DatabaseError, connections, transaction
from django.db.models import Q
from django.forms.utils import flatatt
from django.utils.html import format_html

from .imagenes import MAX_BYTES_POR_IMAGEN, MB, procesar_imagen

logger = logging.getLogger(__name__)

CAMPO = "imagen"  # el original
CAMPO_DETALLE = "imagen_detalle"  # la versión optimizada
CAMPOS = (CAMPO, CAMPO_DETALLE)
# Contrato con `core.upload_paths`: `colecciones/<uuid>.<ext>` para el original
# y `colecciones/derivados/<uuid>.webp` para la versión optimizada. Del disco
# solo se borra lo que tenga exactamente una de esas dos formas.
_RUTA_DE_PORTADA = re.compile(
    r"colecciones/(?:[A-Za-z0-9_-]+\.[A-Za-z0-9]+|derivados/[A-Za-z0-9_-]+\.webp)"
)

# Solo orienta al elegir el archivo: lo que decide es su contenido real.
TIPOS_ACEPTADOS = "image/jpeg,image/png,image/webp"
# De estos nombres solo se usa la extensión: en el disco cada archivo se llama con un UUID.
NOMBRE_DEL_ORIGINAL = "portada"
NOMBRE_DEL_DETALLE = "detalle.webp"
ANCHO_VISTA_PREVIA = 96

AYUDA_PORTADA = (
    f"JPG, PNG o WebP de hasta {MAX_BYTES_POR_IMAGEN // MB} MB. "
    "Se conserva el original y la tienda usa una versión optimizada. "
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
            _direccion_de_vista_previa(datos["value"]),
            ANCHO_VISTA_PREVIA,
            selector,
            casilla,
        )


def _direccion_de_vista_previa(archivo):
    """La versión optimizada de esa portada; si no la tiene, el propio archivo.

    `archivo` es el valor de `Coleccion.imagen`: el original, que puede pesar
    varios megas. Para una vista previa de 96 px basta la versión optimizada.
    """
    detalle = getattr(getattr(archivo, "instance", None), CAMPO_DETALLE, None)
    return (detalle or archivo).url


class PortadaProcesada(ContentFile):
    """El original limpio de una portada, que lleva consigo su versión optimizada.

    Es lo que entrega `CampoPortada`. Al guardar, `Coleccion.save()` escribe
    este archivo en `imagen` y `detalle` en `imagen_detalle`.
    """

    def __init__(self, resultado):
        super().__init__(
            resultado.original,
            name=f"{NOMBRE_DEL_ORIGINAL}{resultado.extension_original}",
        )
        self.detalle = resultado.detalle


class CampoPortada(forms.FileField):
    """Campo de formulario de la portada: valida, limpia y optimiza la imagen.

    Lo que devuelve —y por tanto lo que el modelo guarda— NO es el archivo tal
    como lo subió la persona, sino lo que entrega `core.imagenes`: el original
    ya limpio y, con él, su versión optimizada (`PortadaProcesada`).
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
        return PortadaProcesada(procesar_imagen(archivo))  # ValidationError con el motivo


# ---------------------------------------------------------------------------
# Archivos en el disco
# ---------------------------------------------------------------------------

def _nombre(coleccion, campo):
    """Nombre del archivo que el objeto en memoria lleva en `campo` ("" si no tiene)."""
    return getattr(coleccion, campo).name or ""


def archivos_de(coleccion):
    """Nombres de los archivos de portada que lleva el objeto: original y versión optimizada."""
    return tuple(nombre for nombre in (_nombre(coleccion, campo) for campo in CAMPOS) if nombre)


def _nombres_guardados(coleccion):
    """Los archivos que la base de datos tiene AHORA para esa colección, por campo."""
    fila = None
    if coleccion.pk is not None:
        fila = type(coleccion).objects.filter(pk=coleccion.pk).values(*CAMPOS).first()
    return {campo: (fila[campo] if fila else "") or "" for campo in CAMPOS}


def _subida_pendiente(archivo):
    """El archivo recién asignado al campo que todavía no se escribió en el disco, o None."""
    # Así distingue el propio Django (`FileField.pre_save`) un archivo por escribir.
    if archivo and not archivo._committed:  # pylint: disable=protected-access
        return archivo.file
    return None


def _trae_otro_detalle(coleccion, guardados):
    """True si quien guarda puso en `imagen_detalle` algo distinto de lo guardado."""
    detalle = getattr(coleccion, CAMPO_DETALLE)
    return (
        _subida_pendiente(detalle) is not None
        or (detalle.name or "") != guardados[CAMPO_DETALLE]
    )


def _alinear_detalle(coleccion, guardados):
    """Deja en `imagen_detalle` la versión optimizada de la `imagen` que se va a guardar."""
    original = getattr(coleccion, CAMPO)
    if not original:
        setattr(coleccion, CAMPO_DETALLE, "")  # sin portada no hay versión optimizada
        return
    subida = _subida_pendiente(original)
    detalle = getattr(subida, "detalle", None)
    if detalle:
        # Llega de `CampoPortada`: trae la versión optimizada de ese mismo original.
        # Manda sobre lo que el objeto tuviera en memoria, que puede estar atrasado.
        setattr(coleccion, CAMPO_DETALLE, ContentFile(detalle, name=NOMBRE_DEL_DETALLE))
        return
    otra_portada = subida is not None or original.name != guardados[CAMPO]
    if otra_portada and not _trae_otro_detalle(coleccion, guardados):
        # Otra portada y nadie trae su versión optimizada: la que hay es de la anterior.
        setattr(coleccion, CAMPO_DETALLE, "")


def _borrar(modelo, nombre):
    """Borra el archivo del almacenamiento; devuelve True si lo borró.

    Un fallo del disco (`OSError`) se anota en el registro y no se propaga.
    """
    if not _RUTA_DE_PORTADA.fullmatch(str(nombre or "")):
        logger.warning("No se borra %r: no es un archivo de portada.", nombre)
        return False
    try:
        # Los dos campos usan el mismo almacenamiento.
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
        en_uso = modelo.objects.filter(
            Q(**{CAMPO: nombre}) | Q(**{CAMPO_DETALLE: nombre})
        ).exists()
    except DatabaseError:
        logger.exception("No se pudo comprobar si la portada %r sigue en uso.", nombre)
        return False
    if en_uso:
        return False
    return _borrar(modelo, nombre)


def programar_borrado(modelo, *nombres):
    """Al confirmarse la transacción, borra los archivos que ninguna colección use.

    Sin transacción abierta se ejecuta en el momento. Si la transacción se
    revierte, no se ejecuta: los archivos siguen en su sitio.

    Cada archivo se programa por separado y con `robust=True`: si uno falla
    —incluso con un error que nadie previó—, el otro se borra igualmente y
    quien guardó no recibe ningún error. Ese error imprevisto lo anota Django
    (`django.db.backends.base`), no este módulo.
    """
    for nombre in nombres:
        if nombre:
            # `nombre=nombre` fija el valor de ESTA vuelta del bucle.
            transaction.on_commit(
                lambda nombre=nombre: borrar_si_nadie_la_usa(modelo, nombre), robust=True
            )


def _transaccion_condenada(modelo):
    """True dentro de una transacción que, tras un error, ya solo puede revertirse.

    En ese estado Django no deja consultar la base de datos; tampoco hace falta:
    nada de lo escrito en esa transacción va a quedar.
    """
    conexion = connections[modelo.objects.db]
    return conexion.in_atomic_block and conexion.needs_rollback


def _descartar_recien_escritos(modelo, nombres):
    """Borra los archivos que un guardado fallido alcanzó a escribir.

    Devuelve True si borró alguno. Se intentan todos: un fallo con uno —sea
    cual sea— no impide intentar el otro ni tapa el error del guardado, que es
    el que debe llegar a quien guardó. Queda anotado en el registro.
    """
    alguno = False
    for nombre in nombres:
        try:
            if _transaccion_condenada(modelo):
                borrado = _borrar(modelo, nombre)
            else:
                # Fuera de una transacción (o si el fallo llegó después de
                # escribir la fila) se comprueba primero: si la fila sí quedó
                # guardada, el archivo es suyo.
                borrado = borrar_si_nadie_la_usa(modelo, nombre)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("No se pudo descartar %r tras un guardado fallido.", nombre)
            borrado = False
        alguno = alguno or borrado
    return alguno


@contextmanager
def cuidar_archivos(coleccion, solo_campos=None):
    """Rodea a `Coleccion.save()`: el disco y la base de datos no deben separarse.

    `solo_campos` es el `update_fields` de ese guardado (None: todos los campos).
    Si no incluye la portada, aquí no se hace nada.

    - Antes de guardar, deja en `imagen_detalle` la versión optimizada que
      corresponde a la `imagen` que se va a guardar (ver el inicio del módulo).
    - Si el guardado falla después de escribir archivos nuevos, se borran (no
      quedan huérfanos) y el objeto vuelve a apuntar a la portada que tiene la
      base de datos, para que un reintento no guarde una ruta rota ni mezcle el
      original de una portada con la versión optimizada de otra.
    - Si el guardado sale bien y la portada cambió (otra fotografía, o ninguna),
      los archivos anteriores se borran al confirmarse la transacción, y solo
      si ninguna colección los sigue usando.
    """
    modelo = type(coleccion)
    campos = tuple(campo for campo in CAMPOS if solo_campos is None or campo in solo_campos)
    guardados = _nombres_guardados(coleccion) if campos else {}
    if CAMPO in campos:
        _alinear_detalle(coleccion, guardados)
    al_empezar = {campo: _nombre(coleccion, campo) for campo in campos}
    try:
        yield
    except Exception:
        # El nombre solo cambia durante el guardado cuando se escribe un archivo.
        escritos = [
            _nombre(coleccion, campo)
            for campo in campos
            if _nombre(coleccion, campo) not in ("", al_empezar[campo])
        ]
        if _descartar_recien_escritos(modelo, escritos):
            for campo in campos:
                setattr(coleccion, campo, guardados[campo])
        raise
    programar_borrado(
        modelo,
        *(guardados[campo] for campo in campos if guardados[campo] != _nombre(coleccion, campo)),
    )
