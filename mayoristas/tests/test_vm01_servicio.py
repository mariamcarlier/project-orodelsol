from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from mayoristas.models import SolicitudMayorista
from mayoristas.servicios import registrar_solicitud

DATOS = {
    "tipo_persona": "EMPRESA", "nit": "900.123.456-7",
    "nombre_comercial": "Joyería Aurora", "representante_legal": "Ana Pérez",
    "ciudad": "Bogotá", "telefono": "3001234567",
    "correo": "aurora@ejemplo.com", "canal_venta": "Redes sociales",
}


def crear_usuario(nombre):
    return get_user_model().objects.create_user(
        username=nombre, email=f"{nombre}@ejemplo.com", password="Clave-segura-123")


class RegistrarSolicitudTests(TestCase):
    def setUp(self):
        self.ana = crear_usuario("ana")

    def test_queda_pendiente_y_sin_acceso(self):
        s = registrar_solicitud(self.ana, DATOS)
        self.assertEqual(s.estado, "PENDIENTE")
        self.ana.refresh_from_db()
        self.assertNotEqual(self.ana.rol, "MAYORISTA")

    def test_ignora_estado_enviado_por_el_usuario(self):
        s = registrar_solicitud(self.ana, {**DATOS, "estado": "APROBADA"})
        self.assertEqual(s.estado, "PENDIENTE")

    def test_normaliza_el_nit(self):
        self.assertEqual(registrar_solicitud(self.ana, DATOS).nit, "900123456-7")

    def test_rechaza_nit_invalido(self):
        with self.assertRaises(ValidationError):
            registrar_solicitud(self.ana, {**DATOS, "nit": "12ab"})

    def test_una_sola_solicitud_activa_por_usuario(self):
        registrar_solicitud(self.ana, DATOS)
        with self.assertRaises(ValidationError):
            registrar_solicitud(self.ana, {**DATOS, "nit": "800111222"})

    def test_nit_repetido_de_otro_usuario(self):
        registrar_solicitud(self.ana, DATOS)
        with self.assertRaises(ValidationError):
            registrar_solicitud(crear_usuario("luis"), DATOS)

    def test_tras_un_rechazo_puede_volver_a_solicitar(self):
        s = registrar_solicitud(self.ana, DATOS)
        s.estado = "RECHAZADA"
        s.save()
        self.assertEqual(registrar_solicitud(self.ana, DATOS).estado, "PENDIENTE")

    def test_la_base_de_datos_tambien_protege(self):
        registrar_solicitud(self.ana, DATOS)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SolicitudMayorista.objects.create(
                usuario=self.ana, **{**DATOS, "nit": "800111222"})