from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from configuracion.models import Idioma, Impuesto, Moneda, ParametroGeneral

from .dashboard import RECURSOS, construir_menu, construir_migas
from .models import Coleccion, Producto


class InicioCatalogoTests(TestCase):
    def test_inicio_muestra_productos_desde_la_base_de_datos(self):
        coleccion = Coleccion.objects.create(
            nombre="Colección de prueba",
            temporada="2026",
        )
        Producto.objects.create(
            coleccion=coleccion,
            nombre="Anillo de prueba",
            precio="1250000.00",
            activo=True,
        )

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Anillo de prueba")
        self.assertContains(response, "Colección de prueba")


class PanelAdministracionTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_superuser(
            username="administrador",
            password="clave-de-prueba",
            first_name="Admin",
            last_name="Prueba",
            tipo_documento="CC",
            documento="123456789",
            fecha_nacimiento=date(1990, 1, 1),
            telefono="3001234567",
        )
        self.client.force_login(usuario)

    def test_cada_recurso_usa_la_plantilla_compartida(self):
        for recurso in RECURSOS:
            with self.subTest(recurso=recurso["key"]):
                response = self.client.get(
                    reverse(
                        "core:admin_section",
                        kwargs={"seccion": recurso["key"]},
                    )
                )

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "admin_custom/section.html")
                self.assertContains(response, recurso["title"])
                self.assertContains(response, "Ir a la tienda")

    def test_resumen_enlaza_a_las_paginas_de_recursos(self):
        response = self.client.get(reverse("core:admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        for recurso in RECURSOS:
            with self.subTest(recurso=recurso["key"]):
                self.assertContains(
                    response,
                    reverse(
                        "core:admin_section",
                        kwargs={"seccion": recurso["key"]},
                    ),
                )
                self.assertContains(response, recurso["description"])

    def test_seccion_actual_se_marca_como_pagina_activa(self):
        response = self.client.get(
            reverse("core:admin_section", kwargs={"seccion": "impuestos"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("core:admin_section", kwargs={"seccion": "impuestos"})}" '
            'aria-current="page"',
        )

    def test_usuario_con_rol_admin_pero_sin_is_staff_no_accede_al_panel(self):
        usuario = get_user_model().objects.create_user(
            username="admin_sin_staff",
            password="password123",
            rol="ADMIN",
            first_name="Admin",
            last_name="Sin acceso",
            tipo_documento="CC",
            documento="987654321",
            fecha_nacimiento=date(1990, 1, 1),
        )
        self.client.force_login(usuario)

        response = self.client.get(
            reverse("core:admin_section", kwargs={"seccion": "impuestos"})
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_staff_sin_permiso_de_modelo_no_accede_a_la_seccion(self):
        usuario = get_user_model().objects.create_user(
            username="staff_sin_permiso",
            password="password123",
            is_staff=True,
            first_name="Staff",
            last_name="Sin permiso",
            tipo_documento="CC",
            documento="876543210",
            fecha_nacimiento=date(1990, 1, 1),
        )
        self.client.force_login(usuario)

        response = self.client.get(
            reverse("core:admin_section", kwargs={"seccion": "impuestos"})
        )

        self.assertEqual(response.status_code, 403)

    def test_staff_con_permiso_de_modelo_puede_ver_la_seccion(self):
        usuario = get_user_model().objects.create_user(
            username="staff_con_permiso",
            password="password123",
            is_staff=True,
            first_name="Staff",
            last_name="Con permiso",
            tipo_documento="CC",
            documento="765432109",
            fecha_nacimiento=date(1990, 1, 1),
        )
        permiso_ver_impuesto = Permission.objects.get(
            content_type__app_label="configuracion",
            codename="view_impuesto",
        )
        usuario.user_permissions.add(permiso_ver_impuesto)
        self.client.force_login(usuario)

        response = self.client.get(
            reverse("core:admin_section", kwargs={"seccion": "impuestos"})
        )

        self.assertEqual(response.status_code, 200)

    def test_editar_permisos_de_grupo_actualiza_acceso_de_sus_miembros(self):
        grupo = Group.objects.create(name="Operadores de catálogo")
        permiso_anterior = Permission.objects.get(
            content_type__app_label="core",
            codename="view_producto",
        )
        permiso_nuevo = Permission.objects.get(
            content_type__app_label="core",
            codename="change_producto",
        )
        grupo.permissions.add(permiso_anterior)
        miembro = get_user_model().objects.create_user(
            username="miembro_catalogo",
            password="PruebaSegura123!",
            is_staff=True,
            first_name="Miembro",
            last_name="Catálogo",
            tipo_documento="CC",
            documento="345678901",
            fecha_nacimiento=date(1990, 1, 1),
        )
        miembro.groups.add(grupo)
        url = reverse("core:admin_section", kwargs={"seccion": "grupos"})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Permisos del grupo")
        self.assertContains(response, "dashboard-form--groups")
        self.assertContains(response, "dashboard-field--permissions")
        self.assertContains(response, "dashboard-permissions")
        self.assertContains(response, "· Cambiar")
        self.assertContains(
            response,
            "Los usuarios miembros del grupo reciben estos permisos.",
        )
        self.assertRegex(
            response.content.decode(),
            rf'<input[^>]*name="grupos-{grupo.pk}-permissions"'
            rf'[^>]*value="{permiso_anterior.pk}"[^>]*checked',
        )

        response = self.client.post(
            url,
            {
                "recurso": "grupos",
                "accion": "edit",
                "registro": grupo.pk,
                f"grupos-{grupo.pk}-name": grupo.name,
                f"grupos-{grupo.pk}-permissions": [permiso_nuevo.pk],
            },
        )

        self.assertRedirects(response, f"{url}#registros")
        grupo.refresh_from_db()
        self.assertQuerySetEqual(
            grupo.permissions.order_by("pk"),
            [permiso_nuevo],
        )
        miembro_actualizado = get_user_model().objects.get(pk=miembro.pk)
        self.assertTrue(miembro_actualizado.has_perm("core.change_producto"))
        self.assertFalse(miembro_actualizado.has_perm("core.view_producto"))

    def test_staff_sin_permiso_para_cambiar_grupos_no_puede_modificarlos(self):
        grupo = Group.objects.create(name="Grupo protegido")
        permiso_ver_grupo = Permission.objects.get(
            content_type__app_label="auth",
            codename="view_group",
        )
        permiso_cambiar_producto = Permission.objects.get(
            content_type__app_label="core",
            codename="change_producto",
        )
        usuario = get_user_model().objects.create_user(
            username="staff_solo_lectura_grupos",
            password="PruebaSegura123!",
            is_staff=True,
            first_name="Staff",
            last_name="Lectura",
            tipo_documento="CC",
            documento="456789012",
            fecha_nacimiento=date(1990, 1, 1),
        )
        usuario.user_permissions.add(permiso_ver_grupo)
        self.client.force_login(usuario)
        url = reverse("core:admin_section", kwargs={"seccion": "grupos"})

        response = self.client.post(
            url,
            {
                "recurso": "grupos",
                "accion": "edit",
                "registro": grupo.pk,
                f"grupos-{grupo.pk}-name": grupo.name,
                f"grupos-{grupo.pk}-permissions": [permiso_cambiar_producto.pk],
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(grupo.permissions.exists())

    def test_crear_impuesto_desde_el_panel_respeta_nombre_unico(self):
        url = reverse("core:admin_section", kwargs={"seccion": "impuestos"})
        impuesto = Impuesto.objects.create(nombre="IVA", tasa="19.00")

        response = self.client.post(url, {
            "recurso": "impuestos",
            "accion": "create",
            "impuestos-nuevo-nombre": "IVA",
            "impuestos-nuevo-tasa": "16.00",
            "impuestos-nuevo-vigente": "on",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Impuesto.objects.count(), 1)
        impuesto.refresh_from_db()
        self.assertEqual(impuesto.tasa, Decimal("19.00"))

    def test_crear_impuesto_desde_el_panel(self):
        url = reverse("core:admin_section", kwargs={"seccion": "impuestos"})

        response = self.client.post(url, {
            "recurso": "impuestos",
            "accion": "create",
            "impuestos-nuevo-nombre": "IVA",
            "impuestos-nuevo-tasa": "19.00",
            "impuestos-nuevo-vigente": "on",
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Impuesto.objects.get().nombre, "IVA")

    def test_listado_del_panel_muestra_los_registros(self):
        Impuesto.objects.create(nombre="IVA", tasa="19.00")
        url = reverse("core:admin_section", kwargs={"seccion": "impuestos"})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "IVA")
        self.assertContains(response, "19.00")

    def test_crear_moneda_principal_desmarca_la_anterior(self):
        Moneda.objects.create(
            codigo_iso="COP",
            nombre="Peso colombiano",
            simbolo="$",
            es_principal=True,
        )
        url = reverse("core:admin_section", kwargs={"seccion": "monedas"})

        response = self.client.post(url, {
            "recurso": "monedas",
            "accion": "create",
            "monedas-nuevo-codigo_iso": "USD",
            "monedas-nuevo-nombre": "Dólar estadounidense",
            "monedas-nuevo-simbolo": "$",
            "monedas-nuevo-tasa_cambio": "1.0000",
            "monedas-nuevo-es_principal": "on",
            "monedas-nuevo-activa": "on",
        })

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Moneda.objects.get(codigo_iso="COP").es_principal)
        self.assertTrue(Moneda.objects.get(codigo_iso="USD").es_principal)

    def test_rechazar_moneda_con_codigo_iso_duplicado(self):
        Moneda.objects.create(
            codigo_iso="COP",
            nombre="Peso colombiano",
            simbolo="$",
        )
        url = reverse("core:admin_section", kwargs={"seccion": "monedas"})

        response = self.client.post(url, {
            "recurso": "monedas",
            "accion": "create",
            "monedas-nuevo-codigo_iso": "COP",
            "monedas-nuevo-nombre": "Peso duplicado",
            "monedas-nuevo-simbolo": "$",
            "monedas-nuevo-tasa_cambio": "1.0000",
            "monedas-nuevo-activa": "on",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Moneda.objects.count(), 1)

    def test_crear_idioma_principal_desmarca_el_anterior(self):
        Idioma.objects.create(codigo="es", nombre="Español", es_principal=True)
        url = reverse("core:admin_section", kwargs={"seccion": "idiomas"})

        response = self.client.post(url, {
            "recurso": "idiomas",
            "accion": "create",
            "idiomas-nuevo-codigo": "en",
            "idiomas-nuevo-nombre": "English",
            "idiomas-nuevo-es_principal": "on",
            "idiomas-nuevo-activo": "on",
        })

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Idioma.objects.get(codigo="es").es_principal)
        self.assertTrue(Idioma.objects.get(codigo="en").es_principal)

    def test_rechazar_idioma_con_codigo_duplicado(self):
        Idioma.objects.create(codigo="es", nombre="Español")
        url = reverse("core:admin_section", kwargs={"seccion": "idiomas"})

        response = self.client.post(url, {
            "recurso": "idiomas",
            "accion": "create",
            "idiomas-nuevo-codigo": "es",
            "idiomas-nuevo-nombre": "Español duplicado",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Idioma.objects.count(), 1)

    def test_editar_parametros_registra_usuario_y_fecha_de_actualizacion(self):
        parametros = ParametroGeneral.get_solo()
        url = reverse("core:admin_section", kwargs={"seccion": "parametros"})

        response = self.client.post(url, {
            "recurso": "parametros",
            "accion": "edit",
            "registro": parametros.pk,
            f"parametros-{parametros.pk}-nombre_tienda": "Oro del Sol actualizado",
            f"parametros-{parametros.pk}-lema": "Joyería fina",
            f"parametros-{parametros.pk}-nit": "901.999.888-1",
            f"parametros-{parametros.pk}-correo_contacto": "info@orodelsol.com",
            f"parametros-{parametros.pk}-telefono_contacto": "3001234567",
            f"parametros-{parametros.pk}-direccion": "Carrera 15",
            f"parametros-{parametros.pk}-ciudad": "Bogotá",
            f"parametros-{parametros.pk}-horario_atencion": "Lunes a viernes",
        })

        self.assertEqual(response.status_code, 302)
        parametros.refresh_from_db()
        self.assertEqual(parametros.nombre_tienda, "Oro del Sol actualizado")
        self.assertEqual(parametros.actualizado_por.username, "administrador")
        self.assertIsNotNone(parametros.fecha_actualizacion)

    def test_editar_parametros_rechaza_nombre_obligatorio_vacio(self):
        parametros = ParametroGeneral.get_solo()
        nombre_original = parametros.nombre_tienda
        url = reverse("core:admin_section", kwargs={"seccion": "parametros"})

        response = self.client.post(url, {
            "recurso": "parametros",
            "accion": "edit",
            "registro": parametros.pk,
            f"parametros-{parametros.pk}-nombre_tienda": "",
            f"parametros-{parametros.pk}-lema": "",
            f"parametros-{parametros.pk}-nit": "901.999.888-1",
            f"parametros-{parametros.pk}-correo_contacto": "info@orodelsol.com",
            f"parametros-{parametros.pk}-telefono_contacto": "3001234567",
            f"parametros-{parametros.pk}-direccion": "Carrera 15",
            f"parametros-{parametros.pk}-ciudad": "Bogotá",
            f"parametros-{parametros.pk}-horario_atencion": "",
        })

        self.assertEqual(response.status_code, 200)
        parametros.refresh_from_db()
        self.assertEqual(parametros.nombre_tienda, nombre_original)
        self.assertTrue(response.context["recurso"]["filas"][0]["formulario"].errors)

    def test_parametros_generales_no_permiten_crear_un_segundo_registro(self):
        ParametroGeneral.get_solo()
        url = reverse("core:admin_section", kwargs={"seccion": "parametros"})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["recurso"]["crear_formulario"])


class MenuLateralTests(TestCase):
    CLAVES_CONFIGURACION = [
        "parametros",
        "impuestos",
        "monedas",
        "idiomas",
        "costos_envio",
        "metodos_pago",
        "politicas_comerciales",
        "plantillas_documentos",
    ]
    CLAVES_SUELTAS = ["productos", "colecciones", "usuarios", "grupos"]

    def crear_staff(self, username, documento, codenames=()):
        usuario = get_user_model().objects.create_user(
            username=username,
            password="password123",
            is_staff=True,
            first_name="Staff",
            last_name="Prueba",
            tipo_documento="CC",
            documento=documento,
            fecha_nacimiento=date(1990, 1, 1),
        )
        for codename in codenames:
            usuario.user_permissions.add(
                Permission.objects.get(codename=codename)
            )
        return usuario

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

    def url_seccion(self, clave):
        return reverse("core:admin_section", kwargs={"seccion": clave})

    def claves(self, entradas):
        return [entrada["recurso"]["key"] for entrada in entradas]

    def test_configuracion_aparece_agrupada_y_ordenada(self):
        response = self.client.get(reverse("core:admin_dashboard"))

        menu = response.context["menu_lateral"]
        self.assertEqual(len(menu["grupos"]), 1)
        grupo = menu["grupos"][0]
        self.assertEqual(grupo["title"], "Configuración")
        self.assertEqual(self.claves(grupo["items"]), self.CLAVES_CONFIGURACION)
        self.assertEqual(self.claves(menu["sueltos"]), self.CLAVES_SUELTAS)
        self.assertContains(response, "<summary>")

    def test_grupo_cerrado_en_el_resumen(self):
        response = self.client.get(reverse("core:admin_dashboard"))

        self.assertFalse(response.context["menu_lateral"]["grupos"][0]["abierto"])
        self.assertContains(response, "<details>")
        self.assertNotContains(response, "<details open>")

    def test_grupo_se_abre_al_visitar_un_submodulo(self):
        for clave in self.CLAVES_CONFIGURACION:
            with self.subTest(seccion=clave):
                response = self.client.get(self.url_seccion(clave))

                self.assertTrue(response.context["menu_lateral"]["grupos"][0]["abierto"])
                self.assertContains(response, "<details open>")

    def test_submodulo_activo_se_identifica_correctamente(self):
        response = self.client.get(self.url_seccion("monedas"))

        grupo = response.context["menu_lateral"]["grupos"][0]
        activos = [e["recurso"]["key"] for e in grupo["items"] if e["activo"]]
        self.assertEqual(activos, ["monedas"])
        self.assertFalse(any(e["activo"] for e in response.context["menu_lateral"]["sueltos"]))

        enlace_activo = f'href="{self.url_seccion("monedas")}" aria-current="page"'
        self.assertContains(response, enlace_activo, count=1)
        self.assertNotContains(
            response, f'href="{self.url_seccion("impuestos")}" aria-current="page"'
        )

    def test_recurso_suelto_activo_no_abre_el_grupo(self):
        response = self.client.get(self.url_seccion("productos"))

        menu = response.context["menu_lateral"]
        activos = [e["recurso"]["key"] for e in menu["sueltos"] if e["activo"]]
        self.assertEqual(activos, ["productos"])
        self.assertFalse(menu["grupos"][0]["abierto"])
        self.assertNotContains(response, "<details open>")

    def test_permisos_filtran_los_submodulos_visibles(self):
        usuario = self.crear_staff("solo_impuestos", "111", ["view_impuesto"])
        self.client.force_login(usuario)

        response = self.client.get(self.url_seccion("impuestos"))

        menu = response.context["menu_lateral"]
        self.assertEqual(self.claves(menu["grupos"][0]["items"]), ["impuestos"])
        self.assertEqual(menu["sueltos"], [])
        self.assertNotContains(response, self.url_seccion("monedas"))

    def test_grupo_no_aparece_si_no_hay_permiso_sobre_sus_submodulos(self):
        usuario = self.crear_staff("solo_productos", "222", ["view_producto"])
        self.client.force_login(usuario)

        response = self.client.get(reverse("core:admin_dashboard"))

        menu = response.context["menu_lateral"]
        self.assertEqual(menu["grupos"], [])
        self.assertEqual(self.claves(menu["sueltos"]), ["productos"])
        self.assertNotContains(response, "menu-group")

    def test_el_servidor_sigue_bloqueando_submodulos_sin_permiso(self):
        usuario = self.crear_staff("solo_impuestos_2", "333", ["view_impuesto"])
        self.client.force_login(usuario)

        response = self.client.get(self.url_seccion("monedas"))

        self.assertEqual(response.status_code, 403)

    def test_costos_envio_conserva_ruta_e_icono(self):
        recurso = next(r for r in RECURSOS if r["key"] == "costos_envio")
        self.assertEqual(recurso["icon"], "bxs-truck")

        response = self.client.get(reverse("core:admin_dashboard"))

        self.assertContains(response, f'href="{self.url_seccion("costos_envio")}"')
        self.assertContains(response, "bxs-truck")
        self.assertNotContains(response, "bx-truck")

    def test_el_resto_del_menu_sigue_funcionando(self):
        response = self.client.get(reverse("core:admin_dashboard"))

        for clave in self.CLAVES_SUELTAS:
            with self.subTest(recurso=clave):
                self.assertContains(response, f'href="{self.url_seccion(clave)}"')
                self.assertEqual(
                    self.client.get(self.url_seccion(clave)).status_code, 200
                )
        self.assertContains(response, "Resumen")
        self.assertContains(response, "Ir a la tienda")

    def test_construir_menu_ignora_recursos_sin_grupo_conocido(self):
        recursos = [
            {"key": "a", "grupo": "no_existe"},
            {"key": "b"},
        ]

        menu = construir_menu(recursos, "a")

        self.assertEqual(menu["grupos"], [])
        self.assertEqual(self.claves(menu["sueltos"]), ["a", "b"])


class MigasTests(TestCase):
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

    def titulos(self, migas):
        return [miga["title"] for miga in migas]

    def test_migas_del_resumen(self):
        response = self.client.get(reverse("core:admin_dashboard"))

        migas = response.context["migas"]
        self.assertEqual(self.titulos(migas), ["Mi cuenta", "Admin"])
        self.assertEqual(migas[0]["url"], reverse("usuarios:perfil"))
        self.assertIsNone(migas[1]["url"])
        self.assertContains(response, 'aria-label="Migas de pan"')

    def test_migas_de_un_submodulo_incluyen_el_grupo(self):
        url = reverse("core:admin_section", kwargs={"seccion": "impuestos"})
        response = self.client.get(url)

        migas = response.context["migas"]
        self.assertEqual(
            self.titulos(migas), ["Mi cuenta", "Admin", "Configuración", "Impuestos"]
        )
        self.assertEqual(migas[1]["url"], reverse("core:admin_dashboard"))
        self.assertIsNone(migas[2]["url"])
        self.assertIsNone(migas[3]["url"])
        self.assertContains(
            response, f'<a href="{reverse("core:admin_dashboard")}">Admin</a>'
        )

    def test_migas_de_un_recurso_sin_grupo(self):
        url = reverse("core:admin_section", kwargs={"seccion": "productos"})
        response = self.client.get(url)

        self.assertEqual(
            self.titulos(response.context["migas"]),
            ["Mi cuenta", "Admin", "Productos"],
        )

    def test_construir_migas_con_clave_desconocida_no_falla(self):
        migas = construir_migas("no_existe")

        self.assertEqual(self.titulos(migas), ["Mi cuenta", "Admin"])


class ResponsivePanelTests(TestCase):
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

    def test_la_pagina_incluye_boton_de_menu_overlay_y_script(self):
        response = self.client.get(reverse("core:admin_dashboard"))

        self.assertContains(response, 'id="menuToggle"')
        self.assertContains(response, 'aria-controls="sidebar"')
        self.assertContains(response, 'aria-expanded="false"')
        self.assertContains(response, 'id="dashboardOverlay"')
        self.assertContains(response, "js/dashboard.js")


class ColeccionCBVTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_user(
            username="crud",
            password="PruebaSegura123!",
            first_name="Usuario",
            last_name="Prueba",
            tipo_documento="CC",
            documento="987654321",
            fecha_nacimiento=date(1995, 5, 10),
            telefono="3007654321",
        )
        self.client.force_login(usuario)

    def test_listado_muestra_titulo_y_colecciones(self):
        Coleccion.objects.create(nombre="Luz Dorada", temporada="Clásica")

        response = self.client.get(reverse("core:coleccion_listar"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Colecciones")
        self.assertContains(response, "Luz Dorada")

    def test_crear_y_actualizar_coleccion(self):
        create_response = self.client.post(
            reverse("core:coleccion_crear"),
            {
                "nombre": "Luz Dorada",
                "descripcion": "Diseños clásicos",
                "temporada": "Clásica",
                "imagen_url": "",
                "activa": "on",
            },
        )
        coleccion = Coleccion.objects.get(nombre="Luz Dorada")

        self.assertRedirects(create_response, reverse("core:coleccion_listar"))

        update_response = self.client.post(
            reverse("core:coleccion_editar", kwargs={"pk": coleccion.pk}),
            {
                "nombre": "Luz Dorada 2026",
                "descripcion": "Diseños clásicos actualizados",
                "temporada": "2026",
                "imagen_url": "",
                "activa": "on",
            },
        )
        coleccion.refresh_from_db()

        self.assertRedirects(update_response, reverse("core:coleccion_listar"))
        self.assertEqual(coleccion.nombre, "Luz Dorada 2026")

    def test_eliminar_coleccion_por_post(self):
        coleccion = Coleccion.objects.create(nombre="Temporal")

        response = self.client.post(
            reverse("core:coleccion_eliminar", kwargs={"pk": coleccion.pk})
        )

        self.assertRedirects(response, reverse("core:coleccion_listar"))
        self.assertFalse(Coleccion.objects.filter(pk=coleccion.pk).exists())

    def test_eliminar_coleccion_con_productos_muestra_error(self):
        coleccion = Coleccion.objects.create(nombre="Con productos")
        Producto.objects.create(
            coleccion=coleccion,
            nombre="Anillo de prueba",
            precio="100000.00",
        )

        response = self.client.post(
            reverse("core:coleccion_eliminar", kwargs={"pk": coleccion.pk}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tiene productos asociados")
        self.assertTrue(Coleccion.objects.filter(pk=coleccion.pk).exists())


class AuthenticationViewTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="acceso",
            email="acceso@example.com",
            password="PruebaSegura123!",
            first_name="Usuario",
            last_name="Autenticado",
            tipo_documento="CC",
            documento="123450987",
            fecha_nacimiento=date(1992, 3, 14),
            telefono="3001230098",
        )

    def test_login_view_muestra_formulario_y_conserva_next(self):
        response = self.client.get(
            reverse("core:iniciar_sesion"),
            {"next": reverse("core:producto_listar")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")
        self.assertContains(response, 'name="csrfmiddlewaretoken"', html=False)
        self.assertContains(response, 'name="next"', html=False)

    def test_login_y_logout(self):
        login_response = self.client.post(
            reverse("core:iniciar_sesion"),
            {"email": self.usuario.email, "password": "PruebaSegura123!"},
        )
        self.assertRedirects(login_response, reverse("usuarios:perfil"))

        logout_response = self.client.post(reverse("core:cerrar_sesion"))
        self.assertRedirects(logout_response, reverse("core:iniciar_sesion"))

    def test_logout_rechaza_get(self):
        response = self.client.get(reverse("core:cerrar_sesion"))

        self.assertEqual(response.status_code, 405)