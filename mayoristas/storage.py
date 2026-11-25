"""Almacenamiento privado de documentos (VM-19, DEC-10).

DEC-10 es tajante: los documentos del mayorista son sensibles y **nunca** van a
`MEDIA_ROOT`, porque todo lo que hay en `MEDIA_ROOT` se sirve públicamente
bajo `/media/` en cuanto `DEBUG=True`, y en producción queda expuesto si el
servidor web apunta ahí. Un RUT o una Cámara de Comercio con enlace público es
una fuga de datos personales de un tercero.

Cómo se resuelve:

- `PRIVATE_MEDIA_ROOT` es un directorio hermano de `MEDIA_ROOT`, fuera de
  `MEDIA_URL`. Ningún `static()` ni `media()` lo sirve.
- `AlmacenamientoPrivado` es un `FileSystemStorage` sobre ese directorio. No
  tiene `.url()` utilizable para descargas: la descarga pasa SIEMPRE por una
  vista que comprueba permisos y devuelve el archivo con `FileResponse`.
- El nombre del archivo se genera con un `upload_to` que incluye el id de la
  solicitud y un sufijo aleatorio, para que dos personas no se pisen y para
  que adivinar una ruta sea inviable.
"""

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible

# Directorio fuera de MEDIA_URL. Se puede sobreescribir en settings si algún
# día se mueve a un volumen distinto.
RUTA_PRIVADA = getattr(
    settings, "PRIVATE_MEDIA_ROOT", Path(settings.BASE_DIR) / "media-privado"
)


@deconstructible
class AlmacenamientoPrivado(FileSystemStorage):
    """`FileSystemStorage` privado: sin URL pública.

    Ojo con un detalle que NO es obvio: en `FileSystemStorage`, pasar
    `base_url=None` **no** desactiva la URL, la deja caer en `MEDIA_URL`
    (`_value_or_setting(None, settings.MEDIA_URL)`). El resultado sería
    `/media/solicitudes/1/<uuid>.pdf`: una ruta pública con un UUID difícil de
    adivinar, que es *seguridad por oscuridad*, no control de acceso.

    Por eso se sobrescriben `base_url` y `url()`: cualquier intento de obtener
    un enlace directo falla con `ValueError`. La única forma de leer un
    documento es la vista autorizada que devuelve `FileResponse`.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("location", RUTA_PRIVADA)
        super().__init__(*args, **kwargs)

    @property
    def base_url(self):
        return None

    def url(self, name):
        raise ValueError(
            "Los documentos del canal mayorista son privados: no tienen URL. "
            "Se descargan por `mayoristas:descargar_documento`, que comprueba "
            "permisos."
        )


almacenamiento_privado = AlmacenamientoPrivado()


def ruta_documento(instancia, nombre_original):
    """Ruta dentro del almacén privado: `solicitudes/<id>/<uuid>-<nombre>`.

    Se conserva el nombre original (saneado) porque quien revisa necesita
    reconocer el archivo, y se antepone un UUID para que no colisionen dos
    documentos con el mismo nombre de archivo.
    """
    from pathlib import Path as _Path

    sufijo = _Path(nombre_original).suffix.lower()[:10]
    return f"solicitudes/{instancia.solicitud_id}/{uuid.uuid4().hex}{sufijo}"
