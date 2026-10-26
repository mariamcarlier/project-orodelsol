"""Pruebas del catálogo con variantes (Producto / VarianteProducto)."""

import importlib
from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .dashboard import ProductoForm
from .models import Coleccion, Material, Producto, Talla, VarianteProducto


def crear_producto(**extra):
    coleccion, _ = Coleccion.objects.get_or_create(nombre="Alma Dorada")
    datos = {
        "coleccion": coleccion,
        "nombre": "Anillo Aurora",
        "precio": Decimal("1000000.00"),
        "imagen_url": "https://example.com/aurora.jpg",
    }
    datos.update(extra)
    return Producto.objects.create(**datos)


class CodigoProductoTests(TestCase):
    def test_codigo_se_autogenera_desde_el_mayor_ya_usado(self):
        crear_producto(codigo="AN-0007")
        siguiente = crear_producto(nombre="Otro anillo")

        self.assertEqual(siguiente.codigo, "AN-0008")

    def test_codigo_se_normaliza_a_mayusculas(self):
        producto = crear_producto(codigo=" an-0001 ")

        self.assertEqual(producto.codigo, "AN-0001")

    def test_codigo_es_unico_en_la_base_de_datos(self):
        crear_producto(codigo="AN-0001")

        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_producto(nombre="Otro anillo", codigo="an-0001")


class PublicacionProductoTests(TestCase):
    def test_clean_exige_nombre_precio_e_imagen_para_publicar(self):
        coleccion = Coleccion.objects.create(nombre="Colección")
        producto = Producto(
            coleccion=coleccion,
            nombre="",
            precio=Decimal("0"),
            imagen_url="",
            activo=True,
        )

        with self.assertRaises(ValidationError) as ctx:
            producto.full_clean()

        self.assertTrue(
            {"nombre", "precio", "imagen_url"} <= set(ctx.exception.message_dict)
        )

    def test_un_borrador_no_exige_imagen(self):
        coleccion = Coleccion.objects.create(nombre="Colección")
        producto = Producto(
            coleccion=coleccion,
            nombre="Anillo",
            precio=Decimal("100.00"),
            imagen_url="",
            activo=True,
            es_borrador=True,
        )

        producto.full_clean()  # no debe lanzar

    def test_borrador_e_inactivo_no_aparecen_en_el_catalogo_publico(self):
        visible = crear_producto(nombre="Anillo Visible")
        crear_producto(nombre="Anillo Oculto", es_borrador=True)
        crear_producto(nombre="Anillo Inactivo", activo=False)

        respuesta = self.client.get("/")

        self.assertContains(respuesta, "Anillo Visible")
        self.assertNotContains(respuesta, "Anillo Oculto")
        self.assertNotContains(respuesta, "Anillo Inactivo")
        self.assertEqual(list(Producto.objects.publicos()), [visible])

    def test_el_conteo_de_la_coleccion_ignora_los_borradores(self):
        crear_producto(nombre="Anillo Visible")
        crear_producto(nombre="Anillo Oculto", es_borrador=True)

        respuesta = self.client.get("/")

        self.assertEqual(respuesta.context["colecciones"][0].producto_count, 1)


class TallaTests(TestCase):
    def test_representacion_en_texto(self):
        self.assertEqual(str(Talla(talla_us=Decimal("7.0"))), "US 7")
        self.assertEqual(str(Talla(talla_us=Decimal("6.5"))), "US 6.5")
        self.assertEqual(str(Talla(talla_us=Decimal("10.0"))), "US 10")
        verificada = Talla(
            talla_us=Decimal("7.0"),
            diametro_interno_mm=Decimal("17.30"),
            diametro_verificado=True,
        )
        self.assertEqual(str(verificada), "US 7 (17.3 mm)")

    def test_verificada_exige_diametro(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Talla.objects.create(talla_us=Decimal("7.0"), diametro_verificado=True)

    def test_diametro_debe_ser_positivo(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Talla.objects.create(
                talla_us=Decimal("7.0"), diametro_interno_mm=Decimal("0")
            )


class VarianteProductoTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(codigo="AN-0001")
        self.talla = Talla.objects.create(talla_us=Decimal("7.0"))
        self.otra_talla = Talla.objects.create(talla_us=Decimal("8.0"))
        self.oro = Material.objects.create(nombre="Oro amarillo 18K")
        self.producto.tallas.add(self.talla)
        self.producto.materiales.add(self.oro)

    def crear(self, **extra):
        datos = {
            "producto": self.producto,
            "talla": self.talla,
            "material": self.oro,
            "sku": "AN-0001-7-OA",
        }
        datos.update(extra)
        return VarianteProducto.objects.create(**datos)

    def test_sku_es_unico(self):
        self.crear()

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear(talla=self.otra_talla, sku="an-0001-7-oa")

    def test_variante_duplicada_se_rechaza_en_la_base_de_datos(self):
        self.crear()

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear(sku="OTRO-SKU")

    def test_clean_rechaza_talla_y_material_no_permitidos(self):
        blanco = Material.objects.create(nombre="Oro blanco 18K")
        variante = VarianteProducto(
            producto=self.producto,
            talla=self.otra_talla,
            material=blanco,
            sku="X-1",
        )

        with self.assertRaises(ValidationError) as ctx:
            variante.full_clean()

        self.assertIn("talla", ctx.exception.message_dict)
        self.assertIn("material", ctx.exception.message_dict)

    def test_clean_acepta_talla_y_material_permitidos(self):
        variante = VarianteProducto(
            producto=self.producto,
            talla=self.talla,
            material=self.oro,
            sku="OK-1",
        )

        variante.full_clean()  # no debe lanzar

    def test_peso_cero_o_negativo_se_rechaza_en_la_base_de_datos(self):
        for peso in (Decimal("0"), Decimal("-1.50")):
            with self.subTest(peso=peso):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.crear(peso_gramos=peso)

    def test_peso_cero_tambien_falla_en_full_clean(self):
        variante = VarianteProducto(
            producto=self.producto,
            talla=self.talla,
            material=self.oro,
            sku="OK-2",
            peso_gramos=Decimal("0"),
        )

        with self.assertRaises(ValidationError):
            variante.full_clean()

    def test_peso_es_opcional_y_acepta_valores_positivos(self):
        sin_peso = self.crear()
        self.assertIsNone(sin_peso.peso_gramos)

        con_peso = self.crear(
            talla=self.otra_talla, sku="AN-0001-8-OA", peso_gramos=Decimal("3.50")
        )
        self.assertEqual(con_peso.peso_gramos, Decimal("3.50"))

    def test_precio_adicional_negativo_se_rechaza(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear(precio_adicional=Decimal("-1.00"))

    def test_stock_negativo_se_rechaza(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear(stock=-1)

    def test_precio_final_es_precio_base_mas_adicional(self):
        variante = self.crear(precio_adicional=Decimal("50000.00"))

        self.assertEqual(variante.precio_final, Decimal("1050000.00"))

    def test_sku_se_normaliza_a_mayusculas(self):
        variante = self.crear(sku=" an-0001-7-oa ")

        self.assertEqual(variante.sku, "AN-0001-7-OA")

    def test_no_se_puede_borrar_una_talla_o_material_con_variantes(self):
        self.crear()

        with self.assertRaises(ProtectedError):
            self.talla.delete()
        with self.assertRaises(ProtectedError):
            self.oro.delete()


class SeedTallasMaterialesTests(TestCase):
    def ejecutar(self):
        call_command("seed_tallas_materiales", stdout=StringIO())

    def test_carga_los_valores_base(self):
        self.ejecutar()

        self.assertEqual(
            list(Material.objects.values_list("nombre", flat=True)),
            ["Oro amarillo 18K"],
        )
        self.assertEqual(Talla.objects.count(), 19)
        self.assertFalse(Talla.objects.filter(diametro_verificado=True).exists())

    def test_es_idempotente_y_no_pisa_lo_editado(self):
        self.ejecutar()
        talla = Talla.objects.get(talla_us=Decimal("7.0"))
        talla.diametro_interno_mm = Decimal("17.30")
        talla.diametro_verificado = True
        talla.save()

        self.ejecutar()

        self.assertEqual(Talla.objects.count(), 19)
        self.assertEqual(Material.objects.count(), 1)
        talla.refresh_from_db()
        self.assertTrue(talla.diametro_verificado)
        self.assertEqual(talla.diametro_interno_mm, Decimal("17.30"))

    # NUEVO TEST DE LA FASE B1
    def test_carga_diametros_y_talla_nacional(self):
        self.ejecutar()
        talla_7 = Talla.objects.get(talla_us=Decimal("7.0"))
        self.assertEqual(talla_7.diametro_interno_mm, Decimal("17.30"))
        self.assertEqual(talla_7.talla_nacional, "12")
        self.assertFalse(talla_7.diametro_verificado)

        talla_13 = Talla.objects.get(talla_us=Decimal("13.0"))
        self.assertEqual(talla_13.diametro_interno_mm, Decimal("22.30"))
        self.assertEqual(talla_13.talla_nacional, "24")


class PanelProductosVariantesTests(TestCase):
    def setUp(self):
        administrador = get_user_model().objects.create_superuser(
            username="administrador",
            password="clave-de-prueba",
            first_name="Admin",
            last_name="Prueba",
            tipo_documento="CC",
            documento="123456789",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
        )
        self.client.force_login(administrador)
        self.url = reverse("core:admin_section", kwargs={"seccion": "productos"})

    def datos_creacion(self, coleccion, **extra):
        datos = {
            "recurso": "productos",
            "accion": "create",
            "productos-nuevo-coleccion": coleccion.pk,
            "productos-nuevo-nombre": "Anillo Panel",
            "productos-nuevo-precio": "1500000",
            "productos-nuevo-imagen_url": "https://example.com/panel.jpg",
            "productos-nuevo-activo": "on",
        }
        datos.update(extra)
        return datos

    def test_crear_producto_genera_codigo_y_guarda_tallas(self):
        coleccion = Coleccion.objects.create(nombre="Panel")
        talla = Talla.objects.create(talla_us=Decimal("7.0"))

        respuesta = self.client.post(
            self.url,
            self.datos_creacion(coleccion, **{"productos-nuevo-tallas": [talla.pk]}),
        )

        self.assertEqual(respuesta.status_code, 302)
        producto = Producto.objects.get(nombre="Anillo Panel")
        self.assertEqual(producto.codigo, "AN-0001")
        self.assertEqual(list(producto.tallas.all()), [talla])

    def test_no_se_publica_sin_imagen_pero_si_como_borrador(self):
        coleccion = Coleccion.objects.create(nombre="Panel")
        sin_imagen = {"productos-nuevo-imagen_url": ""}

        respuesta = self.client.post(self.url, self.datos_creacion(coleccion, **sin_imagen))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "La imagen es obligatoria para publicar")
        self.assertEqual(Producto.objects.count(), 0)

        borrador = {**sin_imagen, "productos-nuevo-es_borrador": "on"}
        respuesta = self.client.post(self.url, self.datos_creacion(coleccion, **borrador))

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Producto.objects.get(nombre="Anillo Panel").es_borrador)

    def test_accion_masiva_no_activa_productos_incompletos(self):
        completo = crear_producto(nombre="Completo", activo=False)
        incompleto = crear_producto(nombre="Incompleto", activo=False, imagen_url="")

        self.client.post(
            self.url,
            {
                "recurso": "productos",
                "accion": "bulk",
                "estado": "1",
                "registros": [completo.pk, incompleto.pk],
            },
        )

        completo.refresh_from_db()
        incompleto.refresh_from_db()
        self.assertTrue(completo.activo)
        self.assertFalse(incompleto.activo)

    def test_el_codigo_queda_bloqueado_al_editar(self):
        producto = crear_producto(codigo="AN-0001")

        self.assertFalse(ProductoForm().fields["codigo"].disabled)
        self.assertTrue(ProductoForm(instance=producto).fields["codigo"].disabled)


class MigracionCodigosTests(TransactionTestCase):
    """La migración de datos 0004 conserva los productos y no repite códigos."""

    migrate_from = [("core", "0003_catalogo_variantes_esquema")]
    migrate_to = [("core", "0004_asignar_codigo_productos")]

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.addCleanup(self.volver_al_esquema_actual)
        apps = executor.loader.project_state(self.migrate_from).apps

        Coleccion = apps.get_model("core", "Coleccion")
        Producto = apps.get_model("core", "Producto")
        coleccion = Coleccion.objects.create(nombre="Histórica")
        for nombre, codigo in (
            ("Uno", None),
            ("Dos", "AN-0007"),
            ("Tres", ""),
            ("Cuatro", None),
        ):
            Producto.objects.create(
                coleccion=coleccion, nombre=nombre, precio="100.00", codigo=codigo
            )

    def volver_al_esquema_actual(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def codigos(self, apps):
        Producto = apps.get_model("core", "Producto")
        return list(Producto.objects.order_by("pk").values_list("codigo", flat=True))

    def test_conserva_los_productos_y_asigna_codigos_unicos(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps

        codigos = self.codigos(apps)

        self.assertEqual(len(codigos), 4)
        self.assertEqual(len(set(codigos)), 4)
        # El código ya existente se conserva y el contador sigue desde el mayor.
        self.assertEqual(codigos, ["AN-0008", "AN-0007", "AN-0009", "AN-0010"])

    def test_es_idempotente(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        antes = self.codigos(apps)

        modulo = importlib.import_module("core.migrations.0004_asignar_codigo_productos")
        modulo.asignar_codigos(apps, None)

        self.assertEqual(self.codigos(apps), antes)
