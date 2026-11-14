"""Ejecuta las pruebas de portadas como si el sistema de archivos fuera Windows.

Para qué sirve
--------------
Django construye el nombre que recibe el almacenamiento con
`os.path.normpath`, que en Windows devuelve `colecciones\\derivados\\<id>.webp`.
Este script hace que ese nombre salga con «\\» aunque se ejecute en Linux o
macOS, para comprobar que las pruebas de fallo parcial funcionan en los dos
sistemas. Fue lo que destapó que aquí pasaban sin probar nada.

Cómo se usa
-----------
    python scripts/pruebas/como_windows.py

Con el argumento `--todas` ejecuta además la suite completa.
Sale con código 0 si todo va bien y 1 si algo falla.
"""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

import django  # noqa: E402  (después de preparar el entorno)

django.setup()

from django.conf import settings  # noqa: E402
from django.core.files.storage import FileSystemStorage  # noqa: E402
from django.test.utils import get_runner  # noqa: E402

PRUEBAS_DE_FALLO_PARCIAL = [
    # Las cuatro que fallaban en Windows.
    "core.test_portada_coleccion.SinTransaccionAbiertaTests"
    ".test_si_la_version_optimizada_no_se_puede_escribir_no_queda_nada_a_medias",
    "core.test_portada_dos_archivos.FallosParcialesTests"
    ".test_si_la_version_optimizada_no_se_puede_escribir_no_queda_medio_guardada",
    "core.test_portada_dos_archivos.FallosParcialesTests"
    ".test_si_el_original_no_se_puede_escribir_no_se_escribe_nada",
    "core.test_portada_dos_archivos.FallosParcialesTests"
    ".test_si_no_se_llego_a_escribir_nada_un_reintento_guarda_la_portada_nueva",
]

# El único cambio: el nombre que llega al almacenamiento usa «\», como en Windows.
_generar_de_verdad = FileSystemStorage.generate_filename


def generate_filename_como_windows(self, filename):
    return _generar_de_verdad(self, filename).replace("/", "\\")


def main():
    FileSystemStorage.generate_filename = generate_filename_como_windows

    if "--todas" in sys.argv:
        etiquetas = ["core"]
        que = "la suite completa"
    else:
        etiquetas = PRUEBAS_DE_FALLO_PARCIAL
        que = "las pruebas de fallo parcial de portadas"

    print(f"Ejecutando {que} con el separador de rutas de Windows.\n")
    corredor = get_runner(settings)(verbosity=1, interactive=False, keepdb=False)
    fallos = corredor.run_tests(etiquetas)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
