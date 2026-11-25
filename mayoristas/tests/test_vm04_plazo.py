"""Pruebas de VM-04 (JODS-108): plazo de respuesta en días hábiles (RN-VM-06).

El cálculo puro se probó en VM-16. Aquí se comprueba lo que añade esta
historia: dónde se muestra, a quién, con qué texto y qué pasa cuando el
calendario está vacío.

Se fijan fechas con `freeze` manual (parcheando `timezone.localdate` y
`auto_now_add`), porque un plazo depende de qué día es hoy y una prueba que
depende del calendario real falla los domingos.

Regla del calendario (RN-VM-06, confirmada por la propietaria):
- 24–48 horas hábiles, con jornada de 8 h → 3 y 6 días hábiles.
- La tabla `DiaNoHabil` arranca vacía: solo se descuentan sábados y domingos.
- Sin calendario cargado se AVISA; no se presenta la fecha como exacta.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from mayoristas import festivos, servicios
from mayoristas.models import DiaNoHabil, SolicitudMayorista

Usuario = get_user_model()


def crear_usuario(nombre="mayo", rol="MAYORISTA"):
    return Usuario.objects.create_user(
        username=nombre, email=f"{nombre}@ejemplo.com",
        password="Clave-segura-123", rol=rol,
    )


def crear_revisor(nombre="revisor"):
    usuario = crear_usuario(nombre, rol="ADMIN")
    usuario.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="mayoristas",
            codename__in=["ver_bandeja_solicitudesmayoristas",
                          "gestionar_solicitudesmayoristas"],
        )
    )
    return Usuario.objects.get(pk=usuario.pk)


def crear_solicitud(usuario, nit="900123456", **extra):
    datos = {
        "usuario": usuario,
        "tipo_persona": "JURIDICA",
        "nit": nit,
        "nombre_comercial": "Boutique Sol",
        "representante_legal": "Ana Pérez",
        "ciudad": "Bogotá",
        "telefono": "3001234567",
        "correo": usuario.email,
        "canal_venta": "Tienda física",
    }
    datos.update(extra)
    return SolicitudMayorista.objects.create(**datos)


# Miércoles 4 de marzo de 2026: día hábil, sin festivos alrededor.
MIERCOLES = date(2026, 3, 4)


class PlazoCalculoTests(TestCase):
    """`servicios.plazo_de`: cuándo hay plazo y cuándo no."""

    def setUp(self):
        self.mayorista = crear_usuario()
        self.solicitud = crear_solicitud(self.mayorista)

    def _fijar_creacion(self, fecha):
        """Fija `creado_en` de la solicitud en una fecha concreta."""
        momento = timezone.make_aware(datetime.combine(fecha, datetime.min.time()))
        SolicitudMayorista.objects.filter(pk=self.solicitud.pk).update(
            creado_en=momento
        )
        self.solicitud.refresh_from_db()

    def test_una_solicitud_pendiente_tiene_plazo(self):
        self._fijar_creacion(MIERCOLES)
        plazo = servicios.plazo_de(self.solicitud)
        self.assertIsNotNone(plazo)
        self.assertTrue(plazo["aplicable"])

    def test_la_ventana_es_de_3_a_6_dias_habiles(self):
        """24 h = 3 días hábiles; 48 h = 6. Miércoles + 3 = lunes."""
        self._fijar_creacion(MIERCOLES)
        plazo = servicios.plazo_de(self.solicitud)
        self.assertEqual(plazo["desde"], date(2026, 3, 9))   # lunes
        self.assertEqual(plazo["hasta"], date(2026, 3, 12))  # jueves

    def test_una_solicitud_aprobada_no_muestra_plazo(self):
        self.solicitud.estado = "APROBADA"
        self.solicitud.save(update_fields=["estado"])
        self.assertIsNone(servicios.plazo_de(self.solicitud))

    def test_una_solicitud_rechazada_no_muestra_plazo(self):
        self.solicitud.estado = "RECHAZADA"
        self.solicitud.save(update_fields=["estado"])
        self.assertIsNone(servicios.plazo_de(self.solicitud))

    def test_sin_solicitud_no_hay_plazo(self):
        self.assertIsNone(servicios.plazo_de(None))

    def test_calendario_vacio_avisa(self):
        self._fijar_creacion(MIERCOLES)
        plazo = servicios.plazo_de(self.solicitud)
        self.assertFalse(plazo["calendario_cargado"])
        self.assertIn("calendario", plazo["aviso"].lower())
        self.assertIn("sábados y domingos", plazo["aviso"])

    def test_con_festivos_cargados_el_aviso_cambia(self):
        DiaNoHabil.objects.create(fecha=date(2026, 3, 9), nombre="Prueba")
        self._fijar_creacion(MIERCOLES)
        plazo = servicios.plazo_de(self.solicitud)
        self.assertTrue(plazo["calendario_cargado"])
        self.assertNotIn("aún no está cargado", plazo["aviso"])

    def test_un_festivo_desplaza_la_fecha(self):
        """Si el lunes 9 es festivo, el mínimo pasa al martes 10."""
        DiaNoHabil.objects.create(fecha=date(2026, 3, 9), nombre="Festivo")
        self._fijar_creacion(MIERCOLES)
        plazo = servicios.plazo_de(self.solicitud)
        self.assertEqual(plazo["desde"], date(2026, 3, 10))

    def test_el_texto_dice_la_ventana_y_el_sla(self):
        self._fijar_creacion(MIERCOLES)
        plazo = servicios.plazo_de(self.solicitud)
        self.assertIn("24–48 horas hábiles", plazo["texto"])
        self.assertIn("09/03/2026", plazo["texto"])

    def test_nunca_dice_garantizado(self):
        self._fijar_creacion(MIERCOLES)
        plazo = servicios.plazo_de(self.solicitud)
        texto = (plazo["texto"] + plazo["aviso"]).lower()
        for palabra in ("garantiz", "asegurad", "prometid"):
            self.assertNotIn(palabra, texto)

    def test_dias_restantes_cuenta_dias_habiles(self):
        """Del miércoles 4 al jueves 12 hay 6 hábiles: 5, 6, 9, 10, 11 y 12."""
        self._fijar_creacion(MIERCOLES)
        plazo = servicios.plazo_de(self.solicitud)
        with patch.object(timezone, "localdate", return_value=MIERCOLES):
            self.assertEqual(servicios.dias_restantes(plazo), 6)

    def test_dias_restantes_es_cero_si_ya_paso(self):
        self._fijar_creacion(MIERCOLES)
        plazo = servicios.plazo_de(self.solicitud)
        with patch.object(timezone, "localdate", return_value=date(2026, 4, 1)):
            self.assertEqual(servicios.dias_restantes(plazo), 0)


class PantallaPlazoTests(TestCase):
    """Dónde se ve el plazo y dónde no."""

    def setUp(self):
        self.mayorista = crear_usuario()
        self.solicitud = crear_solicitud(self.mayorista)

    def test_el_mayorista_ve_el_plazo_en_su_estado(self):
        self.client.force_login(self.mayorista)
        respuesta = self.client.get(reverse("mayoristas:mi_solicitud"))
        self.assertContains(respuesta, "Plazo de respuesta estimado")
        self.assertContains(respuesta, "24–48 horas hábiles")

    def test_el_estado_avisa_de_calendario_vacio(self):
        self.client.force_login(self.mayorista)
        respuesta = self.client.get(reverse("mayoristas:mi_solicitud"))
        self.assertContains(respuesta, "calendario de festivos aún no está")

    def test_una_solicitud_aprobada_no_muestra_el_bloque(self):
        self.solicitud.estado = "APROBADA"
        self.solicitud.save(update_fields=["estado"])
        self.client.force_login(self.mayorista)
        respuesta = self.client.get(reverse("mayoristas:mi_solicitud"))
        self.assertNotContains(respuesta, "Plazo de respuesta estimado")

    def test_la_bandeja_muestra_la_columna_plazo(self):
        revisor = crear_revisor()
        self.client.force_login(revisor)
        respuesta = self.client.get(reverse("mayoristas:bandeja"))
        self.assertContains(respuesta, "Plazo")
        self.assertContains(respuesta, "hasta")

    def test_la_bandeja_no_muestra_plazo_de_una_aprobada(self):
        revisor = crear_revisor()
        aprobada = crear_solicitud(
            crear_usuario("otro"), nit="900999999", estado="APROBADA"
        )
        self.client.force_login(revisor)
        respuesta = self.client.get(reverse("mayoristas:bandeja"))
        plazos = [
            s.plazo for s in respuesta.context["solicitudes"] if s.pk == aprobada.pk
        ]
        self.assertEqual(plazos, [None])

    def test_la_revision_muestra_el_plazo(self):
        revisor = crear_revisor()
        self.client.force_login(revisor)
        respuesta = self.client.get(
            reverse("mayoristas:revision", args=[self.solicitud.pk])
        )
        self.assertContains(respuesta, "Plazo de respuesta")
        self.assertContains(respuesta, "24–48 horas hábiles")

    def test_la_revision_de_una_aprobada_no_muestra_plazo(self):
        revisor = crear_revisor()
        self.solicitud.estado = "APROBADA"
        self.solicitud.save(update_fields=["estado"])
        self.client.force_login(revisor)
        respuesta = self.client.get(
            reverse("mayoristas:revision", args=[self.solicitud.pk])
        )
        self.assertIsNone(respuesta.context["plazo"])


class CalendarioAdministrableTests(TestCase):
    """El calendario se edita desde el panel y no se siembra solo."""

    def test_la_tabla_arranca_vacia(self):
        self.assertEqual(DiaNoHabil.objects.count(), 0)

    def test_el_admin_puede_registrar_un_dia_no_habil(self):
        dia = DiaNoHabil.objects.create(
            fecha=date(2026, 1, 1), nombre="Año Nuevo"
        )
        self.assertEqual(str(dia), "01/01/2026 · Año Nuevo")

    def test_un_sabado_no_se_puede_registrar(self):
        from django.core.exceptions import ValidationError

        sabado = date(2026, 3, 7)
        self.assertEqual(sabado.weekday(), 5)
        dia = DiaNoHabil(fecha=sabado, nombre="No")
        with self.assertRaises(ValidationError):
            dia.full_clean()

    def test_un_domingo_no_se_puede_registrar(self):
        from django.core.exceptions import ValidationError

        domingo = date(2026, 3, 8)
        dia = DiaNoHabil(fecha=domingo, nombre="No")
        with self.assertRaises(ValidationError):
            dia.full_clean()

    def test_un_dia_habil_si_se_puede_registrar(self):
        dia = DiaNoHabil(fecha=MIERCOLES, nombre="Cierre")
        dia.full_clean()  # no debe lanzar

    def test_el_calculo_usa_lo_que_hay_en_la_tabla(self):
        DiaNoHabil.objects.create(fecha=date(2026, 3, 5), nombre="Cierre")
        self.assertFalse(festivos.es_habil(date(2026, 3, 5)))
        self.assertTrue(festivos.es_habil(date(2026, 3, 6)))
