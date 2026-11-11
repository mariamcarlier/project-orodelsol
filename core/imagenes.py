"""Validación y procesamiento de imágenes del catálogo (módulo puro).

Este módulo NO toca la base de datos, los modelos ni el almacenamiento: recibe un
archivo subido, comprueba que de verdad es una fotografía aceptable y devuelve
los bytes ya listos para guardar (original limpio + versión de detalle +
miniatura). Quien guarda es otra capa (el servicio de galería, Paso 03b).

Reglas aprobadas (las constantes de abajo son el único lugar donde se cambian):
- Formatos: JPG/JPEG, PNG y WebP, comprobados por el CONTENIDO real del archivo
  y nunca por su extensión o el tipo que declare el navegador. Sin GIF ni SVG.
- Peso: 10 MB por imagen y 30 MB por envío.
- Dimensiones: tope de seguridad de 8000 px por lado y 40 megapíxeles.
- El original se vuelve a codificar: así se elimina cualquier dato oculto
  (EXIF con ubicación GPS, XMP, comentarios) y cualquier carga extra pegada
  al final del archivo. La orientación EXIF se aplica antes de borrarla, para
  que la foto no quede girada.
- Derivados: «detalle» (lado mayor 1200 px) y «miniatura» (400 px), en WebP.
  Nunca se amplía una imagen pequeña.

Decisiones propias de este módulo (a falta de una regla aprobada):
- Las imágenes animadas (GIF, WebP o PNG animado) se rechazan en lugar de
  convertirlas en silencio a su primer cuadro.
- Se conserva el perfil de color ICC si existe, porque es información de color
  y no de privacidad.
"""

from dataclasses import dataclass
from io import BytesIO

from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError

MB = 1024 * 1024

MAX_BYTES_POR_IMAGEN = 10 * MB
MAX_BYTES_POR_ENVIO = 30 * MB
MAX_LADO_PX = 8000
MAX_PIXELES = 40_000_000

LADO_DETALLE_PX = 1200
LADO_MINIATURA_PX = 400
CALIDAD_DERIVADO = 82
CALIDAD_ORIGINAL = 92

# Formato detectado por Pillow -> extensión con la que se guarda el original.
# MPO (JPEG con varias fotos) queda FUERA de la lista aprobada: se rechaza.
EXTENSION_POR_FORMATO = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
FORMATOS_PERMITIDOS = frozenset(EXTENSION_POR_FORMATO)

ERRORES_DE_LECTURA = (OSError, SyntaxError, ValueError, EOFError, Image.DecompressionBombError)


@dataclass(frozen=True)
class ResultadoImagen:
    """Bytes listos para guardar y datos de la imagen ya procesada."""

    original: bytes
    extension_original: str
    detalle: bytes
    miniatura: bytes
    ancho: int
    alto: int
    formato: str


def _error(mensaje, codigo):
    return ValidationError(mensaje, code=codigo)


def _tamano(archivo):
    """Peso en bytes de un archivo subido, sin consumir su contenido."""
    tamano = getattr(archivo, "size", None)
    if tamano is not None:
        return tamano
    posicion = archivo.tell()
    archivo.seek(0, 2)
    total = archivo.tell()
    archivo.seek(posicion)
    return total


def validar_envio(archivos):
    """Comprueba que todas las imágenes de un mismo envío no superen 25 MB."""
    if sum(_tamano(archivo) for archivo in archivos) > MAX_BYTES_POR_ENVIO:
        raise _error(
            f"Las imágenes seleccionadas pesan más de {MAX_BYTES_POR_ENVIO // MB} MB "
            "en total. Envía menos fotografías a la vez.",
            "envio_pesado",
        )


def _leer_bytes(archivo):
    """Lee el archivo completo, sin fiarse del tamaño que declare el cliente."""
    archivo.seek(0)
    datos = archivo.read(MAX_BYTES_POR_IMAGEN + 1)
    archivo.seek(0)
    if not datos:
        raise _error("El archivo está vacío. Selecciona otra imagen.", "vacio")
    if len(datos) > MAX_BYTES_POR_IMAGEN:
        raise _error(
            f"La imagen pesa más de {MAX_BYTES_POR_IMAGEN // MB} MB. "
            "Reduce su tamaño y vuelve a intentarlo.",
            "pesada",
        )
    return datos


def _mensaje_dimensiones(ancho=None, alto=None):
    medida = f"mide {ancho}×{alto} px y " if ancho else ""
    return (
        f"La imagen {medida}supera el máximo permitido: {MAX_LADO_PX} px por lado "
        f"y {MAX_PIXELES // 1_000_000} megapíxeles."
    )


def _abrir_validada(datos):
    """Abre los bytes con Pillow, valida y devuelve (imagen_cargada, formato).

    Todo lo que se comprueba antes de decodificar los píxeles (formato y
    dimensiones) se lee de la cabecera, de modo que un archivo diminuto que
    declara miles de millones de píxeles se rechaza sin gastar memoria.
    """
    try:
        imagen = Image.open(BytesIO(datos))
    except Image.DecompressionBombError as exc:
        raise _error(_mensaje_dimensiones(), "dimensiones") from exc
    except (UnidentifiedImageError, *ERRORES_DE_LECTURA) as exc:
        raise _error(
            "No pudimos reconocer el archivo como una imagen. Usa un archivo JPG, PNG o WebP.",
            "no_imagen",
        ) from exc

    formato = imagen.format
    if formato not in FORMATOS_PERMITIDOS:
        raise _error(
            f"El formato {formato} no está permitido. Usa un archivo JPG, PNG o WebP.",
            "formato",
        )

    ancho, alto = imagen.size
    if max(ancho, alto) > MAX_LADO_PX or ancho * alto > MAX_PIXELES:
        raise _error(_mensaje_dimensiones(ancho, alto), "dimensiones")

    if getattr(imagen, "n_frames", 1) > 1:
        raise _error(
            "Las imágenes animadas no están permitidas. Usa una fotografía fija.",
            "animada",
        )

    try:
        imagen.load()  # decodifica todo: detecta archivos truncados o corruptos
    except ERRORES_DE_LECTURA as exc:
        raise _error(
            "La imagen está dañada o incompleta. Vuelve a exportarla e inténtalo de nuevo.",
            "danada",
        ) from exc
    return imagen, formato


def _con_transparencia(imagen):
    return imagen.mode in ("RGBA", "LA", "PA") or "transparency" in imagen.info


def _normalizar_modo(imagen):
    """Deja la imagen en RGB, RGBA, L o LA (los modos que todos los formatos admiten).

    Debe hacerse ANTES de borrar `imagen.info`, porque en las imágenes de paleta
    la transparencia vive ahí.
    """
    if imagen.mode in ("RGB", "RGBA", "L", "LA"):
        return imagen
    return imagen.convert("RGBA" if _con_transparencia(imagen) else "RGB")


def _para_webp(imagen):
    """WebP solo guarda RGB o RGBA."""
    if imagen.mode in ("RGB", "RGBA"):
        return imagen
    return imagen.convert("RGBA" if imagen.mode == "LA" else "RGB")


def _guardar(imagen, formato, **opciones):
    salida = BytesIO()
    imagen.save(salida, format=formato, **opciones)
    return salida.getvalue()


def _original_limpio(imagen, formato, perfil_icc):
    """Vuelve a codificar la imagen en su mismo formato, sin metadatos."""
    extra = {"icc_profile": perfil_icc} if perfil_icc else {}
    if formato == "JPEG":
        return _guardar(imagen, "JPEG", quality=CALIDAD_ORIGINAL, optimize=True, **extra)
    if formato == "PNG":
        return _guardar(imagen, "PNG", optimize=True, **extra)
    return _guardar(_para_webp(imagen), "WEBP", quality=CALIDAD_ORIGINAL, method=4, **extra)


def _derivado(imagen, lado, perfil_icc):
    """Versión WebP cuyo lado mayor mide como máximo `lado` px (no amplía)."""
    copia = _para_webp(imagen).copy()
    copia.thumbnail((lado, lado), Image.Resampling.LANCZOS)
    extra = {"icc_profile": perfil_icc} if perfil_icc else {}
    return _guardar(copia, "WEBP", quality=CALIDAD_DERIVADO, method=4, **extra)


def validar_imagen(archivo):
    """Valida una imagen subida; lanza ValidationError si no es aceptable."""
    _abrir_validada(_leer_bytes(archivo))


def procesar_imagen(archivo):
    """Valida la imagen y devuelve el original limpio y sus dos derivados."""
    imagen, formato = _abrir_validada(_leer_bytes(archivo))
    perfil_icc = imagen.info.get("icc_profile")
    if imagen.mode in ("CMYK", "YCbCr", "LAB"):
        perfil_icc = None  # un perfil CMYK no describe los colores ya convertidos a RGB
    imagen = ImageOps.exif_transpose(_normalizar_modo(imagen))
    imagen.info = {}  # nada de lo que traía el archivo pasa al resultado

    # Las dimensiones se miden después de girar según EXIF.
    ancho, alto = imagen.size
    return ResultadoImagen(
        original=_original_limpio(imagen, formato, perfil_icc),
        extension_original=EXTENSION_POR_FORMATO[formato],
        detalle=_derivado(imagen, LADO_DETALLE_PX, perfil_icc),
        miniatura=_derivado(imagen, LADO_MINIATURA_PX, perfil_icc),
        ancho=ancho,
        alto=alto,
        formato=formato,
    )
