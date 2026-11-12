"""Pruebas del Paso 1 de la Etapa 4: modelo de la galería de imágenes.

Cubre ProductoImagen (restricciones de base de datos y clean()),
Producto.galeria_gestionada, Coleccion.imagen y que la migración 0007 no
altere los datos existentes. No escribe archivos en disco: las filas con
«archivo» solo guardan un nombre de ruta.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.forms import modelform_factory
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from .dashboard import ProductoForm
from .models import Coleccion, Producto, ProductoImagen


def crear_producto(nombre="Anillo Aurora", **extra):
    coleccion, _ = Coleccion.objects.get_or_create(nombre="Alma Dorada")
    datos = {"coleccion": coleccion, "nombre": nombre, "precio": Decimal("1000000.00")}
    datos.update(extra)
    return Producto.objects.create(**datos)


def url(n):
    return f"https://example.com/{n}.jpg"


class RestriccionesDeBaseDeDatosTests(TestCase):
    """Lo que la base de datos garantiza aunque se salte clean() y el servicio."""

    def setUp(self):
        self.producto = crear_producto()

    def crear(self, **extra):
        return ProductoImagen.objects.create(producto=self.producto, **extra)

    def test_acepta_una_fila_solo_con_url_o_solo_con_archivo(self):
        self.crear(url=url(1))
        self.crear(archivo="productos/1/prueba.jpg")

        self.assertEqual(self.producto.imagenes.count(), 2)

    def test_rechaza_archivo_y_url_a_la_vez(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear(archivo="productos/1/prueba.jpg", url=url(1))

    def test_rechaza_una_fila_sin_ninguna_fuente(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear()

    def test_rechaza_dos_principales_en_el_mismo_producto(self):
        self.crear(url=url(1), es_principal=True)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear(url=url(2), es_principal=True)

    def test_permite_una_principal_por_producto(self):
        otro = crear_producto(nombre="Otro anillo")
        self.crear(url=url(1), es_principal=True)

        ProductoImagen.objects.create(producto=otro, url=url(2), es_principal=True)

        self.assertEqual(ProductoImagen.objects.filter(es_principal=True).count(), 2)

    def test_permite_varias_no_principales(self):
        self.crear(url=url(1), es_principal=True)
        self.crear(url=url(2))
        self.crear(url=url(3))

        self.assertEqual(self.producto.imagenes.filter(es_principal=False).count(), 2)

    def test_cambiar_la_principal_exige_quitar_la_anterior_primero(self):
        # Por esto la principal se cambia en el servicio, con dos UPDATE en este
        # orden, y no con un campo por fila.
        actual = self.crear(url=url(1), es_principal=True)
        nueva = self.crear(url=url(2))

        nueva.es_principal = True
        with self.assertRaises(IntegrityError), transaction.atomic():
            nueva.save()

        with transaction.atomic():
            ProductoImagen.objects.filter(pk=actual.pk).update(es_principal=False)
            ProductoImagen.objects.filter(pk=nueva.pk).update(es_principal=True)
        self.assertEqual(self.producto.imagenes.get(es_principal=True), nueva)

    def test_el_orden_no_es_unico_y_los_empates_se_resuelven_por_pk(self):
        primera = self.crear(url=url(1), orden=2)
        segunda = self.crear(url=url(2), orden=1)
        tercera = self.crear(url=url(3), orden=1)

        self.assertEqual(
            list(self.producto.imagenes.all()), [segunda, tercera, primera]
        )

    def test_valores_por_defecto(self):
        imagen = self.crear(url=url(1))
        imagen.refresh_from_db()

        self.assertFalse(imagen.es_principal)
        self.assertEqual(imagen.orden, 0)
        self.assertIsNotNone(imagen.creado_en)
        self.assertEqual(imagen.archivo.name, "")
        self.assertEqual(imagen.archivo_detalle.name, "")
        self.assertEqual(imagen.archivo_miniatura.name, "")

    def test_borrar_el_producto_borra_sus_imagenes(self):
        self.crear(url=url(1))
        self.crear(url=url(2))

        self.producto.delete()

        self.assertEqual(ProductoImagen.objects.count(), 0)

    def test_save_no_ejecuta_clean_y_la_base_de_datos_es_la_ultima_barrera(self):
        # save() NO valida: con dos fuentes llega a la base y falla con
        # IntegrityError, no con un mensaje legible.
        imagen = ProductoImagen(producto=self.producto, archivo="x.jpg", url=url(1))

        with self.assertRaises(IntegrityError), transaction.atomic():
            imagen.save()


class CleanDeFilaTests(SimpleTestCase):
    """clean() no consulta la base de datos: no hace falta guardar nada."""

    def test_acepta_solo_url(self):
        ProductoImagen(url=url(1)).clean()

    def test_acepta_solo_archivo(self):
        ProductoImagen(archivo="productos/1/prueba.jpg").clean()

    def test_rechaza_ambas_fuentes(self):
        imagen = ProductoImagen(archivo="productos/1/prueba.jpg", url=url(1))

        with self.assertRaisesMessage(ValidationError, "una sola fuente"):
            imagen.clean()

    def test_rechaza_ninguna_fuente(self):
        with self.assertRaisesMessage(ValidationError, "necesita una fuente"):
            ProductoImagen().clean()

    def test_una_url_de_solo_espacios_cuenta_como_vacia(self):
        # La restricción de la base de datos trataría "   " como una URL real.
        with self.assertRaisesMessage(ValidationError, "necesita una fuente"):
            ProductoImagen(url="   ").clean()

    def test_clean_limpia_los_espacios_de_la_url_antes_de_guardar(self):
        imagen = ProductoImagen(archivo="productos/1/prueba.jpg", url="   ")

        imagen.clean()

        self.assertEqual(imagen.url, "")


class CleanFrenteAModelFormTests(TestCase):
    def test_full_clean_detecta_doble_fuente(self):
        producto = crear_producto()
        imagen = ProductoImagen(producto=producto, archivo="x.jpg", url=url(1))

        with self.assertRaises(ValidationError):
            imagen.full_clean()

    def test_un_modelform_sin_los_campos_de_fuente_igualmente_detecta_doble_fuente(self):
        # Django omite las restricciones que tocan campos excluidos del
        # formulario; clean() de fila no se omite. Es el caso del formset de
        # filas existentes (solo «orden»).
        FormularioOrden = modelform_factory(ProductoImagen, fields=("orden",))
        producto = crear_producto()
        imagen = ProductoImagen(producto=producto, archivo="x.jpg", url=url(1))

        formulario = FormularioOrden({"orden": 1}, instance=imagen)

        self.assertFalse(formulario.is_valid())
        self.assertIn("una sola fuente", str(formulario.errors))

    def test_un_modelform_sin_los_campos_de_fuente_acepta_una_fila_correcta(self):
        FormularioOrden = modelform_factory(ProductoImagen, fields=("orden",))
        producto = crear_producto()
        imagen = ProductoImagen(producto=producto, url=url(1))

        self.assertTrue(FormularioOrden({"orden": 3}, instance=imagen).is_valid())


class MensajesDeRestriccionTests(TestCase):
    """Las restricciones de BD hablan en español claro cuando pasan por full_clean()."""

    def test_doble_fuente_en_modelform_no_muestra_el_texto_tecnico_de_django(self):
        FormularioCompleto = modelform_factory(
            ProductoImagen, fields=("archivo", "url", "es_principal", "orden")
        )
        producto = crear_producto()
        formulario = FormularioCompleto(
            {"url": url(1), "orden": 0},
            instance=ProductoImagen(producto=producto, archivo="x.jpg"),
        )

        self.assertFalse(formulario.is_valid())
        texto = str(formulario.errors)
        self.assertNotIn("No se cumple la restricción", texto)
        self.assertNotIn("imagen_una_sola_fuente", texto)

    def test_sin_fuente_en_full_clean_usa_el_mensaje_propio(self):
        imagen = ProductoImagen(producto=crear_producto())

        with self.assertRaises(ValidationError) as contexto:
            imagen.full_clean()

        texto = " ".join(contexto.exception.messages)
        self.assertNotIn("imagen_una_sola_fuente", texto)
        self.assertIn("fuente", texto)

    def test_segunda_principal_en_full_clean_usa_el_mensaje_propio(self):
        producto = crear_producto()
        ProductoImagen.objects.create(
            producto=producto, url=url(1), es_principal=True
        )
        segunda = ProductoImagen(producto=producto, url=url(2), es_principal=True)

        with self.assertRaises(ValidationError) as contexto:
            segunda.full_clean()

        self.assertIn(
            "Un producto solo puede tener una fotografía principal.",
            contexto.exception.messages,
        )

    def test_la_base_de_datos_sigue_rechazando_aunque_se_omita_full_clean(self):
        producto = crear_producto()
        ProductoImagen.objects.create(
            producto=producto, url=url(1), es_principal=True
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductoImagen.objects.create(
                producto=producto, url=url(2), es_principal=True
            )


class ProductoImagenPresentacionTests(TestCase):
    def test_str_no_consulta_la_base_de_datos(self):
        with self.assertNumQueries(0):
            texto = str(ProductoImagen(pk=5, producto_id=9))

        self.assertEqual(texto, "Imagen 5 del producto 9")

    def test_src_solo_url(self):
        imagen = ProductoImagen(url=url(1))

        self.assertEqual(imagen.src, url(1))
        self.assertEqual(imagen.src_miniatura, url(1))
        self.assertEqual(imagen.src_detalle, url(1))

    def test_src_con_archivo_usa_la_ruta_de_medios(self):
        imagen = ProductoImagen(archivo="productos/1/a.jpg")

        self.assertEqual(imagen.src, "/media/productos/1/a.jpg")
        # Sin derivados todavía, miniatura y detalle caen al original.
        self.assertEqual(imagen.src_miniatura, "/media/productos/1/a.jpg")
        self.assertEqual(imagen.src_detalle, "/media/productos/1/a.jpg")

    def test_src_prefiere_los_derivados_cuando_existen(self):
        imagen = ProductoImagen(
            archivo="productos/1/a.jpg",
            archivo_miniatura="productos/1/derivados/m.webp",
            archivo_detalle="productos/1/derivados/d.webp",
        )

        self.assertEqual(imagen.src, "/media/productos/1/a.jpg")
        self.assertEqual(imagen.src_miniatura, "/media/productos/1/derivados/m.webp")
        self.assertEqual(imagen.src_detalle, "/media/productos/1/derivados/d.webp")

    def test_src_sin_ninguna_fuente_devuelve_cadena_vacia(self):
        self.assertEqual(ProductoImagen().src, "")


class MarcadorGaleriaGestionadaTests(TestCase):
    def test_un_producto_nuevo_arranca_sin_galeria_gestionada(self):
        self.assertFalse(crear_producto().galeria_gestionada)

    def test_el_marcador_no_es_editable_en_formularios(self):
        self.assertFalse(Producto._meta.get_field("galeria_gestionada").editable)
        self.assertNotIn("galeria_gestionada", ProductoForm().fields)

    def test_el_marcador_no_altera_imagen_url(self):
        producto = crear_producto(imagen_url=url("historica"))

        producto.galeria_gestionada = True
        producto.save()
        producto.refresh_from_db()

        self.assertEqual(producto.imagen_url, url("historica"))


class PortadaDeColeccionTests(TestCase):
    def test_la_portada_empieza_vacia_y_conserva_imagen_url(self):
        coleccion = Coleccion.objects.create(nombre="Luna", imagen_url=url("luna"))
        coleccion.refresh_from_db()

        self.assertFalse(coleccion.imagen)
        self.assertEqual(coleccion.imagen.name, "")
        self.assertEqual(coleccion.imagen_url, url("luna"))


class MigracionEsquemaGaleriaTests(TransactionTestCase):
    """La 0007 solo agrega: no debe alterar ni perder ninguna fila existente."""

    migrate_from = [("core", "0006_talla_nacional_y_diametros")]
    migrate_to = [("core", "0007_galeria_imagenes_esquema")]

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.addCleanup(self.volver_al_esquema_actual)
        apps = executor.loader.project_state(self.migrate_from).apps

        ColeccionHistorica = apps.get_model("core", "Coleccion")
        ProductoHistorico = apps.get_model("core", "Producto")
        coleccion = ColeccionHistorica.objects.create(
            nombre="Histórica", imagen_url=url("coleccion")
        )
        ProductoHistorico.objects.create(
            coleccion=coleccion, nombre="Con URL", precio="100.00",
            codigo="AN-0001", imagen_url=url("con-url"),
        )
        ProductoHistorico.objects.create(
            coleccion=coleccion, nombre="Sin URL", precio="100.00", codigo="AN-0002",
        )

    def volver_al_esquema_actual(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def aplicar_0007(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        return executor.loader.project_state(self.migrate_to).apps

    def test_conserva_productos_colecciones_e_imagen_url(self):
        apps = self.aplicar_0007()

        Producto = apps.get_model("core", "Producto")
        Coleccion = apps.get_model("core", "Coleccion")

        self.assertEqual(Producto.objects.count(), 2)
        self.assertEqual(
            Producto.objects.get(codigo="AN-0001").imagen_url, url("con-url")
        )
        self.assertEqual(Producto.objects.get(codigo="AN-0002").imagen_url, "")
        coleccion = Coleccion.objects.get()
        self.assertEqual(coleccion.imagen_url, url("coleccion"))
        self.assertEqual(coleccion.imagen, "")

    def test_ningun_producto_queda_marcado_como_gestionado(self):
        apps = self.aplicar_0007()

        Producto = apps.get_model("core", "Producto")

        self.assertFalse(Producto.objects.filter(galeria_gestionada=True).exists())

    def test_no_crea_filas_de_galeria(self):
        # La 0007 solo cambia el esquema. Pasar las URL históricas a la galería
        # es trabajo de una migración de datos aparte, todavía pendiente.
        apps = self.aplicar_0007()

        self.assertEqual(apps.get_model("core", "ProductoImagen").objects.count(), 0)

    def test_es_reversible_mientras_la_galeria_esta_vacia(self):
        self.aplicar_0007()

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        apps = executor.loader.project_state(self.migrate_from).apps

        self.assertEqual(apps.get_model("core", "Producto").objects.count(), 2)

    def _contador(self, tabla):
        with connection.cursor() as cursor:
            cursor.execute("SELECT seq FROM sqlite_sequence WHERE name = %s", [tabla])
            fila = cursor.fetchone()
        return fila[0] if fila else None

    def _crear_y_borrar_el_ultimo(self, modelo, **datos):
        ultimo = modelo.objects.create(**datos)
        pk_borrado = ultimo.pk
        ultimo.delete()
        return pk_borrado

    def test_no_reutiliza_el_id_de_un_producto_borrado(self):
        # SQLite reconstruye la tabla al añadir la columna y, sin cuidado,
        # reinicia el contador AUTOINCREMENT: el id del último producto
        # borrado volvería a asignarse a un producto nuevo.
        executor = MigrationExecutor(connection)
        apps = executor.loader.project_state(self.migrate_from).apps
        coleccion = apps.get_model("core", "Coleccion").objects.get()
        pk_borrado = self._crear_y_borrar_el_ultimo(
            apps.get_model("core", "Producto"),
            coleccion=coleccion, nombre="Efímero", precio="100.00", codigo="AN-9999",
        )

        apps_nuevas = self.aplicar_0007()
        nuevo = apps_nuevas.get_model("core", "Producto").objects.create(
            coleccion_id=coleccion.pk, nombre="Nuevo", precio="100.00", codigo="AN-9998",
        )

        self.assertGreater(nuevo.pk, pk_borrado)

    def test_no_reutiliza_el_id_de_una_coleccion_borrada(self):
        executor = MigrationExecutor(connection)
        apps = executor.loader.project_state(self.migrate_from).apps
        pk_borrado = self._crear_y_borrar_el_ultimo(
            apps.get_model("core", "Coleccion"), nombre="Efímera"
        )

        apps_nuevas = self.aplicar_0007()
        nueva = apps_nuevas.get_model("core", "Coleccion").objects.create(nombre="Nueva")

        self.assertGreater(nueva.pk, pk_borrado)

    def test_el_contador_no_baja_ni_se_inventa_si_no_hay_filas_borradas(self):
        antes_producto = self._contador("core_producto")
        antes_coleccion = self._contador("core_coleccion")

        self.aplicar_0007()

        self.assertEqual(self._contador("core_producto"), antes_producto)
        self.assertEqual(self._contador("core_coleccion"), antes_coleccion)

    def test_con_tablas_vacias_la_migracion_funciona(self):
        executor = MigrationExecutor(connection)
        apps = executor.loader.project_state(self.migrate_from).apps
        apps.get_model("core", "Producto").objects.all().delete()
        apps.get_model("core", "Coleccion").objects.all().delete()

        apps_nuevas = self.aplicar_0007()

        self.assertEqual(apps_nuevas.get_model("core", "Producto").objects.count(), 0)
