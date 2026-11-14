"""Rutas de carga de imágenes (`upload_to`) del catálogo.

ESTE MÓDULO ES ESTABLE: NO RENOMBRAR NI MOVER sus funciones.

Django guarda en cada migración la ruta importable de cada `upload_to`
(por ejemplo `core.upload_paths.ruta_imagen_producto`). Si una función cambia
de nombre o de módulo, las migraciones ya aplicadas dejan de poder cargarse.

Reglas de diseño:
- No importa nada del proyecto, solo la biblioteca estándar. Así `models.py`
  y las migraciones pueden importar este módulo sin dependencias circulares.
- El nombre que escribe el usuario NUNCA llega al disco. El archivo se llama
  con un UUID, y de su nombre original solo se toma la extensión, y solo si
  está en una lista cerrada. Así no hay tildes, espacios ni intentos de ruta
  como «../» en los nombres guardados.
- La carpeta `productos/<id_producto>/` es un contrato: la limpieza de
  archivos (Paso 3) la usa para comprobar que un archivo pertenece al producto
  antes de borrarlo.
- Las formas `colecciones/<uuid>.<ext>` y `colecciones/derivados/<uuid>.webp`
  también son un contrato: `core/portadas.py` solo borra del disco lo que tenga
  exactamente una de esas dos formas.
- Las rutas usan siempre «/», que es como las construye el almacenamiento
  de Django en cualquier sistema operativo.
"""

import os
import uuid

EXTENSIONES_PERMITIDAS = frozenset({".jpg", ".png", ".webp"})
EXTENSION_DESCONOCIDA = ".bin"
SIN_PRODUCTO = "sin-producto"


def _extension_segura(nombre_original):
    """Extensión en minúsculas si está permitida; si no, «.bin».

    Aquí NO se decide si el archivo es de verdad una imagen: eso lo valida el
    contenido real (Paso 3). Esta función solo impide que un nombre
    arbitrario del usuario termine en el disco.
    """
    extension = os.path.splitext(os.path.basename(str(nombre_original or "")))[1].lower()
    if extension == ".jpeg":
        extension = ".jpg"
    return extension if extension in EXTENSIONES_PERMITIDAS else EXTENSION_DESCONOCIDA


def _id_de_producto(instance):
    return getattr(instance, "producto_id", None) or SIN_PRODUCTO


def ruta_imagen_producto(instance, filename):
    """Original: productos/<id_producto>/<uuid>.<ext>"""
    return f"productos/{_id_de_producto(instance)}/{uuid.uuid4().hex}{_extension_segura(filename)}"


def ruta_derivado_producto(instance, filename):
    """Miniatura o versión de detalle: siempre WebP, en la subcarpeta derivados."""
    return f"productos/{_id_de_producto(instance)}/derivados/{uuid.uuid4().hex}.webp"


def ruta_imagen_coleccion(instance, filename):
    """Portada de colección (el original): colecciones/<uuid>.<ext>"""
    return f"colecciones/{uuid.uuid4().hex}{_extension_segura(filename)}"


def ruta_derivado_coleccion(instance, filename):
    """Versión optimizada de la portada: siempre WebP, en la subcarpeta derivados."""
    return f"colecciones/derivados/{uuid.uuid4().hex}.webp"
