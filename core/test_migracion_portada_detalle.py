"""Migración 0010: añade `Coleccion.imagen_detalle` (la versión optimizada de la portada).

Es una migración de esquema: añade una columna vacía y nada más. Aquí se
comprueba, sobre una base de datos con colecciones y productos ya creados, que:

- no altera ni pierde ninguna fila, y no toca ningún archivo;
- se puede deshacer, y al deshacerla las colecciones quedan como estaban;
- no reinicia el contador de ids de las colecciones, ni al aplicarla (en
  SQLite, Django reconstruye la tabla y la migración restaura el contador) ni
  al deshacerla (quitar la columna no reconstruye la tabla).

Las pruebas usan los modelos «históricos» de cada migración, como hace Django
al migrar: así se ejercita la migración y no el código actual de `models.py`.
"""

import shutil
import tempfile
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

ANTES = [("core", "0009_precio_no_negativo")]
DESPUES = [("core", "0010_coleccion_imagen_detalle")]
TABLA = "core_coleccion"
URL_EXTERNA = "https://example.com/portada.jpg"
# Una portada guardada cuando solo existía `imagen`: un único archivo.
ARCHIVO_ANTERIOR = "colecciones/" + "a" * 32 + ".webp"
CAMPOS_DE_SIEMPRE = ("pk", "nombre", "descripcion", "temporada", "imagen_url", "imagen", "activa")


def migrar(destino):
    """Lleva la base de datos a `destino` y devuelve los modelos de ese punto."""
    executor = MigrationExecutor(connection)
    executor.migrate(destino)
    return executor.loader.project_state(destino).apps


def columnas(tabla):
    with connection.cursor() as cursor:
        descripcion = connection.introspection.get_table_description(cursor, tabla)
    return [columna.name for columna in descripcion]


def contador(tabla):
    """El último id que SQLite entregó para esa tabla (None si nunca hubo filas)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT seq FROM sqlite_sequence WHERE name = %s", [tabla])
        fila = cursor.fetchone()
    return fila[0] if fila else None


class _Base(TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.apps = migrar(ANTES)
        self.addCleanup(self.volver_al_esquema_actual)

    def volver_al_esquema_actual(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def colecciones(self, apps, *campos):
        consulta = apps.get_model("core", "Coleccion").objects.order_by("pk")
        return list(consulta.values(*(campos or CAMPOS_DE_SIEMPRE)))


class MigracionPortadaDetalleTests(_Base):
    """La 0010 solo añade la columna: las filas quedan exactamente como estaban."""

    def setUp(self):
        super().setUp()
        Coleccion = self.apps.get_model("core", "Coleccion")
        Producto = self.apps.get_model("core", "Producto")
        con_direccion = Coleccion.objects.create(
            nombre="Con dirección",
            descripcion="Anillos de compromiso",
            temporada="2026",
            imagen_url=URL_EXTERNA,
            activa=False,
        )
        Coleccion.objects.create(nombre="Con archivo", imagen=ARCHIVO_ANTERIOR)
        Coleccion.objects.create(nombre="Sin portada")
        Producto.objects.create(
            coleccion=con_direccion, nombre="Anillo Aurora", precio="100.00", codigo="AN-0001"
        )
        self.antes = self.colecciones(self.apps)
        self.assertEqual(len(self.antes), 3)

    def productos(self, apps):
        consulta = apps.get_model("core", "Producto").objects.order_by("pk")
        return list(consulta.values("pk", "codigo", "nombre", "coleccion_id"))

    def test_antes_de_aplicarla_la_columna_no_existe(self):
        self.assertNotIn("imagen_detalle", columnas(TABLA))

    def test_conserva_todas_las_colecciones_tal_como_estaban(self):
        apps = migrar(DESPUES)

        self.assertEqual(self.colecciones(apps), self.antes)

    def test_la_columna_nueva_llega_vacia_en_todas(self):
        apps = migrar(DESPUES)

        self.assertIn("imagen_detalle", columnas(TABLA))
        self.assertEqual(
            self.colecciones(apps, "imagen_detalle"), [{"imagen_detalle": ""}] * 3
        )

    def test_una_portada_anterior_sigue_en_su_campo_de_siempre(self):
        apps = migrar(DESPUES)

        con_archivo = apps.get_model("core", "Coleccion").objects.get(nombre="Con archivo")
        self.assertEqual(con_archivo.imagen.name, ARCHIVO_ANTERIOR)
        self.assertEqual(con_archivo.imagen_detalle.name, "")

    def test_conserva_los_productos_y_su_coleccion(self):
        antes = self.productos(self.apps)

        apps = migrar(DESPUES)

        self.assertEqual(self.productos(apps), antes)
        connection.check_constraints()  # ninguna referencia apunta a una fila que no existe

    def test_no_crea_ni_borra_ni_cambia_ningun_archivo(self):
        carpeta = tempfile.mkdtemp(prefix="migracion-portada-test-")
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        portada = Path(carpeta) / ARCHIVO_ANTERIOR
        portada.parent.mkdir(parents=True)
        portada.write_bytes(b"portada de siempre")

        with override_settings(MEDIA_ROOT=carpeta):
            migrar(DESPUES)
            migrar(ANTES)

        self.assertEqual([ruta for ruta in Path(carpeta).rglob("*") if ruta.is_file()], [portada])
        self.assertEqual(portada.read_bytes(), b"portada de siempre")

    def test_se_puede_deshacer_y_las_colecciones_quedan_como_estaban(self):
        migrar(DESPUES)

        apps = migrar(ANTES)

        self.assertNotIn("imagen_detalle", columnas(TABLA))
        self.assertEqual(self.colecciones(apps), self.antes)
        self.assertEqual(len(self.productos(apps)), 1)
        connection.check_constraints()

    def test_deshacerla_con_portadas_nuevas_conserva_el_original(self):
        # Una portada subida ya con el esquema nuevo: original y versión optimizada.
        apps = migrar(DESPUES)
        apps.get_model("core", "Coleccion").objects.filter(nombre="Sin portada").update(
            imagen="colecciones/" + "b" * 32 + ".jpg",
            imagen_detalle="colecciones/derivados/" + "c" * 32 + ".webp",
        )

        apps = migrar(ANTES)

        nueva = apps.get_model("core", "Coleccion").objects.get(nombre="Sin portada")
        self.assertEqual(nueva.imagen.name, "colecciones/" + "b" * 32 + ".jpg")

    def test_se_puede_aplicar_deshacer_y_volver_a_aplicar(self):
        migrar(DESPUES)
        migrar(ANTES)

        apps = migrar(DESPUES)

        self.assertEqual(self.colecciones(apps), self.antes)
        self.assertEqual(
            self.colecciones(apps, "imagen_detalle"), [{"imagen_detalle": ""}] * 3
        )


class ContadorDeIdsTests(_Base):
    """SQLite reconstruye la tabla al añadir la columna.

    Sin cuidado, eso reinicia el contador de ids: el id de la última colección
    borrada volvería a asignarse a una colección nueva.
    """

    def crear(self, apps, nombre):
        return apps.get_model("core", "Coleccion").objects.create(nombre=nombre)

    def crear_y_borrar_la_ultima(self, apps):
        self.crear(apps, "Permanente")
        efimera = self.crear(apps, "Efímera")
        pk_borrado = efimera.pk
        efimera.delete()
        return pk_borrado

    def test_al_aplicarla_no_reutiliza_el_id_de_una_coleccion_borrada(self):
        pk_borrado = self.crear_y_borrar_la_ultima(self.apps)

        apps = migrar(DESPUES)

        self.assertGreater(self.crear(apps, "Nueva").pk, pk_borrado)

    def test_al_deshacerla_tampoco_lo_reutiliza(self):
        # Hoy quitar la columna no reconstruye la tabla. Si una versión futura de
        # Django lo hiciera, esta prueba fallaría: habría que cuidar la vuelta.
        apps = migrar(DESPUES)
        pk_borrado = self.crear_y_borrar_la_ultima(apps)

        apps = migrar(ANTES)

        self.assertGreater(self.crear(apps, "Nueva").pk, pk_borrado)

    def test_el_contador_queda_igual_en_los_dos_sentidos(self):
        self.crear_y_borrar_la_ultima(self.apps)
        antes = contador(TABLA)
        self.assertIsNotNone(antes)

        migrar(DESPUES)
        self.assertEqual(contador(TABLA), antes)

        migrar(ANTES)
        self.assertEqual(contador(TABLA), antes)

    def test_sin_filas_borradas_el_contador_no_cambia(self):
        self.crear(self.apps, "Permanente")
        antes = contador(TABLA)

        migrar(DESPUES)

        self.assertEqual(contador(TABLA), antes)

    def test_si_se_borraron_todas_las_colecciones_el_contador_tambien_se_conserva(self):
        pk_borrado = self.crear_y_borrar_la_ultima(self.apps)
        self.apps.get_model("core", "Coleccion").objects.all().delete()

        apps = migrar(DESPUES)

        self.assertGreater(self.crear(apps, "Nueva").pk, pk_borrado)

    def test_con_la_tabla_vacia_funciona_en_los_dos_sentidos(self):
        apps = migrar(DESPUES)
        self.assertEqual(apps.get_model("core", "Coleccion").objects.count(), 0)

        apps = migrar(ANTES)
        self.assertEqual(apps.get_model("core", "Coleccion").objects.count(), 0)

    def test_si_sqlite_no_dejara_fila_de_contador_se_recrea(self):
        # Con este SQLite la reconstrucción siempre deja la fila (a cero si la
        # tabla está vacía). Aquí se imita el caso contrario, llamando a las dos
        # funciones de la migración: sin la fila, el contador no debe perderse.
        migracion = import_module("core.migrations.0010_coleccion_imagen_detalle")
        editor = SimpleNamespace(connection=connection)
        self.crear_y_borrar_la_ultima(self.apps)
        antes = contador(TABLA)

        migracion.guardar_contador(None, editor)
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name = %s", [TABLA])
        self.assertIsNone(contador(TABLA))
        migracion.restaurar_contador(None, editor)

        self.assertEqual(contador(TABLA), antes)

    def test_restaurar_nunca_baja_un_contador(self):
        migracion = import_module("core.migrations.0010_coleccion_imagen_detalle")
        editor = SimpleNamespace(connection=connection)
        self.crear(self.apps, "Uno")

        migracion.guardar_contador(None, editor)
        ultima = self.crear(self.apps, "Dos")  # el contador sube después de guardarlo
        migracion.restaurar_contador(None, editor)

        self.assertEqual(contador(TABLA), ultima.pk)

    def test_no_toca_el_contador_de_los_productos(self):
        Coleccion = self.apps.get_model("core", "Coleccion")
        Producto = self.apps.get_model("core", "Producto")
        coleccion = Coleccion.objects.create(nombre="Permanente")
        Producto.objects.create(
            coleccion=coleccion, nombre="Uno", precio="100.00", codigo="AN-0001"
        )
        efimero = Producto.objects.create(
            coleccion=coleccion, nombre="Dos", precio="100.00", codigo="AN-0002"
        )
        efimero.delete()
        antes = contador("core_producto")

        migrar(DESPUES)

        self.assertEqual(contador("core_producto"), antes)
