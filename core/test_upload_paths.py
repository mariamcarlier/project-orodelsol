"""Pruebas de core/upload_paths.py (Etapa 4, Paso 1).

Estas rutas quedan escritas en las migraciones: lo que se comprueba aquí es lo
que hace estable el módulo (importable, sin dependencias del proyecto) y seguro
(el nombre del usuario no llega al disco).
"""

import inspect
import re
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils.module_loading import import_string

from core import upload_paths

RUTAS_ESTABLES = (
    "core.upload_paths.ruta_imagen_producto",
    "core.upload_paths.ruta_derivado_producto",
    "core.upload_paths.ruta_imagen_coleccion",
)
UUID_HEX = r"[0-9a-f]{32}"


class RutasEstablesTests(SimpleTestCase):
    def test_las_funciones_son_importables_por_su_ruta_de_modulo(self):
        # Esta es la ruta exacta que Django escribe en la migración 0007.
        for ruta in RUTAS_ESTABLES:
            with self.subTest(ruta=ruta):
                self.assertTrue(callable(import_string(ruta)))

    def test_el_modulo_solo_usa_la_biblioteca_estandar(self):
        fuente = inspect.getsource(upload_paths)
        importaciones = re.findall(r"^\s*(?:from|import)\s+(\S+)", fuente, re.MULTILINE)

        self.assertEqual(sorted(set(importaciones)), ["os", "uuid"])


class RutaImagenProductoTests(SimpleTestCase):
    def ruta(self, nombre, producto_id=7):
        return upload_paths.ruta_imagen_producto(
            SimpleNamespace(producto_id=producto_id), nombre
        )

    def test_usa_carpeta_del_producto_uuid_y_extension_permitida(self):
        self.assertRegex(self.ruta("anillo.png"), rf"^productos/7/{UUID_HEX}\.png$")

    def test_dos_cargas_del_mismo_archivo_no_repiten_nombre(self):
        self.assertNotEqual(self.ruta("a.png"), self.ruta("a.png"))

    def test_el_nombre_original_no_llega_al_disco(self):
        for nombre in ("Mi anillo ÁÑ.png", "../../etc/passwd.png", "..\\..\\clave.png"):
            with self.subTest(nombre=nombre):
                ruta = self.ruta(nombre)

                self.assertRegex(ruta, rf"^productos/7/{UUID_HEX}\.png$")
                self.assertNotIn("..", ruta)

    def test_normaliza_extension(self):
        self.assertTrue(self.ruta("A.PNG").endswith(".png"))
        self.assertTrue(self.ruta("a.JPEG").endswith(".jpg"))
        self.assertTrue(self.ruta("a.jpg").endswith(".jpg"))
        self.assertTrue(self.ruta("a.webp").endswith(".webp"))

    def test_extension_no_permitida_se_reemplaza(self):
        for nombre in ("a.gif", "a.svg", "a.php", "a.png.exe", "sin_extension", ".png", ""):
            with self.subTest(nombre=nombre):
                self.assertTrue(self.ruta(nombre).endswith(".bin"))

    def test_producto_sin_id_usa_carpeta_neutra(self):
        self.assertRegex(
            self.ruta("a.png", producto_id=None),
            rf"^productos/sin-producto/{UUID_HEX}\.png$",
        )


class RutaDerivadoProductoTests(SimpleTestCase):
    def test_siempre_webp_y_en_la_subcarpeta_derivados(self):
        instancia = SimpleNamespace(producto_id=7)

        for nombre in ("x.png", "x.jpg", "x.webp", "x.exe"):
            with self.subTest(nombre=nombre):
                self.assertRegex(
                    upload_paths.ruta_derivado_producto(instancia, nombre),
                    rf"^productos/7/derivados/{UUID_HEX}\.webp$",
                )


class RutaImagenColeccionTests(SimpleTestCase):
    def test_usa_carpeta_colecciones_uuid_y_extension_permitida(self):
        ruta = upload_paths.ruta_imagen_coleccion(SimpleNamespace(), "Portada Ñ.JPEG")

        self.assertRegex(ruta, rf"^colecciones/{UUID_HEX}\.jpg$")

    def test_extension_no_permitida_se_reemplaza(self):
        ruta = upload_paths.ruta_imagen_coleccion(SimpleNamespace(), "portada.gif")

        self.assertTrue(ruta.endswith(".bin"))
