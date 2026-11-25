"""Pruebas de VM-16 (JODS-110): tramos de precio y días hábiles.

Se agrupan en tres bloques:

  1. Modelo y restricciones de los tramos.
  2. Cálculo del precio con tramo (DEC-18: sin porcentaje no se calcula).
  3. Días hábiles y calendario de festivos (RN-VM-06).

Ninguna prueba siembra porcentajes: comprueban justamente que el sistema
funciona sin cifras comerciales configuradas.
"""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from mayoristas import selectors
from mayoristas.festivos import (
    dias_habiles_para_horas,
    plazo_de_respuesta,
    sumar_dias_habiles,
)
from mayoristas.models import DiaNoHabil, TramoPrecioReferencia
from mayoristas.servicios import precio_con_tramo


# ─────────────────────────────────────────────────────────────────────
# 1. Modelo
# ─────────────────────────────────────────────────────────────────────

class TramoModeloTests(TestCase):
    def test_el_porcentaje_arranca_vacio(self):
        """DEC-02: no se siembra ningún valor comercial."""
        tramo = TramoPrecioReferencia.objects.create(
            nombre="Medio mayorista", cantidad_minima=10, cantidad_maxima=29
        )
        self.assertIsNone(tramo.porcentaje)
        self.assertFalse(tramo.configurado)

    def test_configurado_cuando_hay_porcentaje(self):
        tramo = TramoPrecioReferencia.objects.create(
            nombre="Mayorista", cantidad_minima=10, cantidad_maxima=29,
            porcentaje=Decimal("5.00"),
        )
        self.assertTrue(tramo.configurado)

    def test_cero_por_ciento_no_es_lo_mismo_que_sin_configurar(self):
        """0 es un valor comercial válido; NULL es «sin definir»."""
        cero = TramoPrecioReferencia.objects.create(
            nombre="Sin descuento", cantidad_minima=10, cantidad_maxima=29,
            porcentaje=Decimal("0.00"),
        )
        vacio = TramoPrecioReferencia.objects.create(
            nombre="Sin definir", cantidad_minima=30, cantidad_maxima=59,
        )
        self.assertTrue(cero.configurado)
        self.assertFalse(vacio.configurado)

    def test_rango_display_para_tramo_sin_limite(self):
        tramo = TramoPrecioReferencia(cantidad_minima=60, cantidad_maxima=None)
        self.assertEqual(tramo.rango_display, "60 o más")

    def test_rango_display_con_limite(self):
        tramo = TramoPrecioReferencia(cantidad_minima=10, cantidad_maxima=29)
        self.assertEqual(tramo.rango_display, "10 – 29")

    def test_la_base_de_datos_rechaza_un_rango_invertido(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            TramoPrecioReferencia.objects.create(
                nombre="Malo", cantidad_minima=50, cantidad_maxima=10
            )

    def test_la_base_de_datos_rechaza_porcentaje_fuera_de_rango(self):
        for malo in (Decimal("-1"), Decimal("101")):
            with self.assertRaises(IntegrityError), transaction.atomic():
                TramoPrecioReferencia.objects.create(
                    nombre="Malo", cantidad_minima=10, cantidad_maxima=29,
                    porcentaje=malo,
                )

    def test_clean_avisa_del_rango_invertido(self):
        tramo = TramoPrecioReferencia(cantidad_minima=50, cantidad_maxima=10)
        with self.assertRaises(ValidationError) as ctx:
            tramo.clean()
        self.assertIn("cantidad_maxima", ctx.exception.message_dict)


# ─────────────────────────────────────────────────────────────────────
# 2. Cálculo del precio (DEC-18)
# ─────────────────────────────────────────────────────────────────────

class PrecioConTramoTests(TestCase):
    def test_sin_tramos_configurados_no_se_calcula_nada(self):
        """DEC-18: la ausencia de cifras comerciales no se rellena sola."""
        resultado = precio_con_tramo(Decimal("100000"), 25)
        self.assertFalse(resultado["calculado"])
        self.assertIsNone(resultado["tramo"])
        self.assertIsNone(resultado["porcentaje"])
        self.assertEqual(resultado["precio_unitario"], Decimal("100000"))
        self.assertEqual(resultado["total"], Decimal("2500000.00"))

    def test_el_tramo_sin_porcentaje_no_se_aplica(self):
        TramoPrecioReferencia.objects.create(
            nombre="Medio", cantidad_minima=10, cantidad_maxima=29
        )
        resultado = precio_con_tramo(Decimal("100000"), 25)
        self.assertFalse(resultado["calculado"])
        self.assertEqual(resultado["precio_unitario"], Decimal("100000"))

    def test_aplica_el_porcentaje_del_tramo_correcto(self):
        TramoPrecioReferencia.objects.create(
            nombre="Medio", cantidad_minima=10, cantidad_maxima=29,
            porcentaje=Decimal("10.00"),
        )
        resultado = precio_con_tramo(Decimal("100000"), 25)
        self.assertTrue(resultado["calculado"])
        self.assertEqual(resultado["precio_unitario"], Decimal("90000.00"))
        self.assertEqual(resultado["total"], Decimal("2250000.00"))

    def test_elige_el_tramo_segun_la_cantidad(self):
        TramoPrecioReferencia.objects.create(
            nombre="Medio", cantidad_minima=10, cantidad_maxima=29,
            porcentaje=Decimal("5.00"),
        )
        TramoPrecioReferencia.objects.create(
            nombre="Alto", cantidad_minima=30, cantidad_maxima=None,
            porcentaje=Decimal("12.50"),
        )
        self.assertEqual(
            precio_con_tramo(Decimal("100000"), 15)["porcentaje"], Decimal("5.00")
        )
        self.assertEqual(
            precio_con_tramo(Decimal("100000"), 40)["porcentaje"], Decimal("12.50")
        )

    def test_el_tramo_abierto_no_tiene_tope(self):
        TramoPrecioReferencia.objects.create(
            nombre="Alto", cantidad_minima=60, cantidad_maxima=None,
            porcentaje=Decimal("15.00"),
        )
        miles = precio_con_tramo(Decimal("100000"), 10000)
        self.assertTrue(miles["calculado"])
        self.assertEqual(miles["porcentaje"], Decimal("15.00"))

    def test_cantidad_por_debajo_del_primer_tramo_no_aplica(self):
        TramoPrecioReferencia.objects.create(
            nombre="Medio", cantidad_minima=10, cantidad_maxima=29,
            porcentaje=Decimal("10.00"),
        )
        resultado = precio_con_tramo(Decimal("100000"), 5)
        self.assertFalse(resultado["calculado"])

    def test_un_tramo_inactivo_no_se_aplica(self):
        TramoPrecioReferencia.objects.create(
            nombre="Medio", cantidad_minima=10, cantidad_maxima=29,
            porcentaje=Decimal("10.00"), activo=False,
        )
        self.assertFalse(precio_con_tramo(Decimal("100000"), 25)["calculado"])

    def test_redondeo_a_dos_decimales(self):
        """99999,99 × 0,6667 = 66 669,993 3… → se redondea a 66 669,99."""
        TramoPrecioReferencia.objects.create(
            nombre="Raro", cantidad_minima=1, cantidad_maxima=None,
            porcentaje=Decimal("33.33"),
        )
        resultado = precio_con_tramo(Decimal("99999.99"), 1)
        self.assertEqual(resultado["precio_unitario"], Decimal("66669.99"))


class SelectoresTramoTests(TestCase):
    def test_hay_tramos_configurados_es_falso_al_principio(self):
        self.assertFalse(selectors.hay_tramos_configurados())

    def test_hay_tramos_configurados_ignora_los_de_sin_porcentaje(self):
        TramoPrecioReferencia.objects.create(
            nombre="Medio", cantidad_minima=10, cantidad_maxima=29
        )
        self.assertFalse(selectors.hay_tramos_configurados())

    def test_tramos_de_referencia_incluye_los_no_configurados(self):
        """La pantalla debe poder decir «definido pero sin cifra»."""
        TramoPrecioReferencia.objects.create(
            nombre="Medio", cantidad_minima=10, cantidad_maxima=29
        )
        self.assertEqual(len(selectors.tramos_de_referencia()), 1)

    def test_tramo_para_cantidad_con_cantidad_cero(self):
        TramoPrecioReferencia.objects.create(
            nombre="Medio", cantidad_minima=1, cantidad_maxima=None,
            porcentaje=Decimal("5.00"),
        )
        self.assertIsNone(selectors.tramo_para_cantidad(0))
        self.assertIsNone(selectors.tramo_para_cantidad(None))


# ─────────────────────────────────────────────────────────────────────
# 3. Días hábiles (RN-VM-06)
# ─────────────────────────────────────────────────────────────────────

class DiasHabilesTests(TestCase):
    # 2026-11-25 es miércoles.
    MIERCOLES = date(2026, 11, 25)
    VIERNES = date(2026, 11, 27)

    def test_24_horas_son_tres_dias_habiles(self):
        self.assertEqual(dias_habiles_para_horas(24), 3)

    def test_48_horas_son_seis_dias_habiles(self):
        self.assertEqual(dias_habiles_para_horas(48), 6)

    def test_cero_horas_no_devuelve_cero(self):
        self.assertEqual(dias_habiles_para_horas(0), 1)

    def test_desde_miercoles_tres_dias_habiles_es_lunes(self):
        """Jueves, viernes, y el lunes: el fin de semana no cuenta."""
        self.assertEqual(sumar_dias_habiles(self.MIERCOLES, 3), date(2026, 11, 30))

    def test_desde_viernes_un_dia_habil_es_lunes(self):
        self.assertEqual(sumar_dias_habiles(self.VIERNES, 1), date(2026, 11, 30))

    def test_un_festivo_en_viernes_empuja_el_plazo(self):
        DiaNoHabil.objects.create(fecha=date(2026, 11, 27), nombre="Festivo")
        self.assertEqual(sumar_dias_habiles(self.MIERCOLES, 2), date(2026, 11, 30))

    def test_cero_dias_devuelve_el_mismo_dia(self):
        self.assertEqual(sumar_dias_habiles(self.MIERCOLES, 0), self.MIERCOLES)

    def test_dias_negativos_no_tienen_sentido(self):
        with self.assertRaises(ValueError):
            sumar_dias_habiles(self.MIERCOLES, -1)

    def test_un_sabado_no_se_puede_registrar_como_festivo(self):
        with self.assertRaises(ValidationError) as ctx:
            DiaNoHabil(fecha=date(2026, 11, 28), nombre="Sábado").clean()
        self.assertIn("fecha", ctx.exception.message_dict)

    def test_plazo_de_respuesta_devuelve_una_ventana(self):
        plazo = plazo_de_respuesta(self.MIERCOLES)
        self.assertEqual(plazo["desde"], date(2026, 11, 30))
        self.assertEqual(plazo["hasta"], date(2026, 12, 3))
        self.assertIn("24–48 horas hábiles", plazo["texto"])
        self.assertFalse(plazo["calendario_cargado"])

    def test_plazo_avisa_si_hay_calendario(self):
        DiaNoHabil.objects.create(fecha=date(2026, 12, 8), nombre="Inmaculada")
        self.assertTrue(plazo_de_respuesta(self.MIERCOLES)["calendario_cargado"])
