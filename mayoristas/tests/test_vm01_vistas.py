"""Pruebas de VM-01 (JODS-95): registro y consulta de la solicitud mayorista.

Se agrupan por capa:
  - Modelo y NIT (normalización, unicidad condicional, re-solicitud).
  - Servicio (lista blanca de campos, estado inicial, concurrencia básica).
  - Vistas (permisos, flujo, deuda del 404, acceso horizontal).
  - Formulario (mensajes por campo).

La base de datos de las pruebas es la temporal de Django: no se toca la de desarrollo ni ningún archivo del repositorio.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from mayoristas.forms import SolicitudMayoristaForm
from mayoristas.models import (
    MENSAJE_NIT,
    SolicitudMayorista,
    normalizar_nit,
)
from mayoristas.servicios import registrar_solicitud

Usuario = get_user_model()

DATOS = {
    "tipo_persona": "EMPRESA",
    "nit": "900.123.456-7",
    "nombre_comercial": "Joyería Aurora",
    "representante_legal": "Ana Pérez",
    "ciudad": "Bogotá",
    "telefono": "3001234567",
    "correo": "aurora@ejemplo.com",
    "canal_venta": "Redes sociales",
    "referido": "Feria de joyería",
}


def crear_usuario(nombre, **extra):
    return Usuario.objects.create_user(
        username=nombre,
        email=f"{nombre}@ejemplo.com",
        password="Clave-segura-123",
        **extra,
    )


# ─────────────────────────────────────────────────────────────────────
# 1. NIT: normalización y unicidad condicional
# ─────────────────────────────────────────────────────────────────────

class NormalizacionNitTests(TestCase):
    def test_normaliza_puntos_y_espacios(self):
        self.assertEqual(normalizar_nit("900.123.456-7"), "900123456-7")
        self.assertEqual(normalizar_nit(" 900 123 456 "), "900123456")
        self.assertEqual(normalizar_nit(""), "")

    def test_el_modelo_guarda_el_nit_canonico(self):
        s = SolicitudMayorista(**{**DATOS, "nit": "900.123.456-7"})
        s.clean_fields(exclude=["usuario"])
        self.assertEqual(s.nit, "900123456-7")

    def test_save_normaliza_aunque_no_se_valide(self):
        """La puerta del ORM directo también deja el NIT canónico."""
        u = crear_usuario("orm")
        s = SolicitudMayorista(usuario=u, **{**DATOS, "nit": "800.111.222-3"})
        s.save()
        s.refresh_from_db()
        self.assertEqual(s.nit, "800111222-3")

    def test_nit_invalido_se_rechaza_con_mensaje_por_campo(self):
        s = SolicitudMayorista(**{**DATOS, "nit": "12ab"})
        with self.assertRaises(ValidationError) as ctx:
            s.clean_fields(exclude=["usuario"])
        self.assertIn("nit", ctx.exception.message_dict)
        self.assertEqual(ctx.exception.message_dict["nit"][0], MENSAJE_NIT)

    def test_los_errores_se_acumulan_en_una_sola_pasada(self):
        """Un formulario debe mostrar todo lo que falta, no solo lo primero."""
        s = SolicitudMayorista(nit="12ab", nombre_comercial="X")
        with self.assertRaises(ValidationError) as ctx:
            s.clean_fields(exclude=["usuario"])
        self.assertIn("nit", ctx.exception.message_dict)
        self.assertIn("ciudad", ctx.exception.message_dict)


class UnicidadNitTests(TestCase):
    def test_puntos_y_sin_puntos_son_el_mismo_nit(self):
        """Núcleo del defecto 6.1: dos escrituras del mismo NIT no pueden convivir."""
        ana = crear_usuario("ana")
        luis = crear_usuario("luis")
        registrar_solicitud(ana, DATOS)

        with self.assertRaises(ValidationError):
            registrar_solicitud(luis, {**DATOS, "nit": "900123456-7"})

        self.assertEqual(SolicitudMayorista.objects.activas().count(), 1)

    def test_la_base_de_datos_bloquea_el_duplicado_normalizado(self):
        """Aunque se salte el servicio, el UniqueConstraint ve el mismo NIT."""
        ana = crear_usuario("ana2")
        luis = crear_usuario("luis2")
        SolicitudMayorista.objects.create(usuario=ana, **DATOS)

        with self.assertRaises(IntegrityError), transaction.atomic():
            SolicitudMayorista.objects.create(
                usuario=luis, **{**DATOS, "nit": "900123456-7"}
            )

    def test_otro_nit_del_mismo_usuario_sigue_bloqueado(self):
        ana = crear_usuario("ana3")
        registrar_solicitud(ana, DATOS)
        with self.assertRaises(ValidationError):
            registrar_solicitud(ana, {**DATOS, "nit": "800999888"})


class UnicidadCondicionalTests(TestCase):
    def test_tras_un_rechazo_el_mismo_nit_puede_volver_a_solicitarse(self):
        ana = crear_usuario("ana4")
        primera = registrar_solicitud(ana, DATOS)
        primera.estado = SolicitudMayorista.Estado.RECHAZADA
        primera.save(update_fields=["estado"])

        segunda = registrar_solicitud(ana, DATOS)

        self.assertEqual(segunda.estado, SolicitudMayorista.Estado.PENDIENTE)
        self.assertEqual(segunda.nit, "900123456-7")
        self.assertEqual(SolicitudMayorista.objects.activas().count(), 1)

    def test_un_rechazo_libera_el_nit_para_otro_usuario(self):
        ana = crear_usuario("ana5")
        luis = crear_usuario("luis5")
        primera = registrar_solicitud(ana, DATOS)
        primera.estado = SolicitudMayorista.Estado.RECHAZADA
        primera.save(update_fields=["estado"])

        segunda = registrar_solicitud(luis, DATOS)

        self.assertEqual(segunda.usuario, luis)


# ─────────────────────────────────────────────────────────────────────
# 2. Servicio
# ─────────────────────────────────────────────────────────────────────

class RegistrarSolicitudServicioTests(TestCase):
    def setUp(self):
        self.ana = crear_usuario("ana6")

    def test_queda_pendiente_y_sin_rol_mayorista(self):
        s = registrar_solicitud(self.ana, DATOS)
        self.assertEqual(s.estado, SolicitudMayorista.Estado.PENDIENTE)
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.rol, "CLIENTE")

    def test_ignora_campos_fuera_de_la_lista_blanca(self):
        s = registrar_solicitud(
            self.ana,
            {**DATOS, "estado": "APROBADA", "motivo_rechazo": "no", "usuario": None},
        )
        self.assertEqual(s.estado, SolicitudMayorista.Estado.PENDIENTE)
        self.assertEqual(s.motivo_rechazo, "")
        self.assertEqual(s.usuario, self.ana)

    def test_una_sola_solicitud_activa_por_usuario(self):
        registrar_solicitud(self.ana, DATOS)
        with self.assertRaises(ValidationError):
            registrar_solicitud(self.ana, {**DATOS, "nit": "700111222"})

    def test_el_estado_inicial_no_se_puede_forzar(self):
        s = registrar_solicitud(self.ana, {**DATOS, "estado": "RECHAZADA"})
        self.assertEqual(s.estado, SolicitudMayorista.Estado.PENDIENTE)


# ─────────────────────────────────────────────────────────────────────
# 3. Formulario
# ─────────────────────────────────────────────────────────────────────

class SolicitudMayoristaFormTests(TestCase):
    def _data(self, **cambios):
        base = {k: v for k, v in DATOS.items()}
        base.update(cambios)
        return base

    def test_acepta_el_nit_con_puntos_y_lo_entrega_limpio(self):
        form = SolicitudMayoristaForm(data=self._data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["nit"], "900123456-7")

    def test_campos_obligatorios_vacios_dan_error_por_campo(self):
        form = SolicitudMayoristaForm(data=self._data(nit="", ciudad=""))
        self.assertFalse(form.is_valid())
        self.assertIn("nit", form.errors)
        self.assertIn("ciudad", form.errors)

    def test_canal_venta_y_referido_son_opcionales(self):
        form = SolicitudMayoristaForm(data=self._data(canal_venta="", referido=""))
        self.assertTrue(form.is_valid(), form.errors)

    def test_correo_con_formato_invalido_se_rechaza(self):
        form = SolicitudMayoristaForm(data=self._data(correo="sin-arroba"))
        self.assertFalse(form.is_valid())
        self.assertIn("correo", form.errors)

    def test_el_formulario_no_expone_el_estado(self):
        self.assertNotIn("estado", SolicitudMayoristaForm().fields)


# ─────────────────────────────────────────────────────────────────────
# 4. Vistas
# ─────────────────────────────────────────────────────────────────────

class SolicitarAccesoTests(TestCase):
    def setUp(self):
        self.url = reverse("mayoristas:solicitar_acceso")

    def test_anonimo_va_al_login(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login/", respuesta["Location"])

    def test_cliente_ve_el_formulario(self):
        self.client.force_login(crear_usuario("cli"))
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "mayoristas/solicitar.html")
        self.assertContains(respuesta, "Solicita tu acceso")

    def test_envio_correcto_crea_pendiente_y_redirige_al_estado(self):
        usuario = crear_usuario("cli2")
        self.client.force_login(usuario)

        respuesta = self.client.post(self.url, DATOS)

        self.assertRedirects(respuesta, reverse("mayoristas:mi_solicitud"))
        solicitud = SolicitudMayorista.objects.get(usuario=usuario)
        self.assertEqual(solicitud.estado, SolicitudMayorista.Estado.PENDIENTE)
        self.assertEqual(solicitud.nit, "900123456-7")

    def test_envio_incompleto_no_crea_nada(self):
        usuario = crear_usuario("cli3")
        self.client.force_login(usuario)

        respuesta = self.client.post(self.url, {**DATOS, "nit": ""})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Este campo es obligatorio")
        self.assertFalse(SolicitudMayorista.objects.filter(usuario=usuario).exists())

    def test_doble_envio_no_duplica(self):
        usuario = crear_usuario("cli4")
        self.client.force_login(usuario)
        self.client.post(self.url, DATOS)

        respuesta = self.client.post(self.url, DATOS)

        self.assertRedirects(respuesta, reverse("mayoristas:mi_solicitud"))
        self.assertEqual(SolicitudMayorista.objects.filter(usuario=usuario).count(), 1)

    def test_un_mayorista_aprobado_no_puede_volver_a_solicitar(self):
        usuario = crear_usuario("may", rol="MAYORISTA")
        SolicitudMayorista.objects.create(
            usuario=usuario, estado=SolicitudMayorista.Estado.APROBADA, **DATOS
        )
        self.client.force_login(usuario)

        respuesta = self.client.get(self.url)

        self.assertRedirects(respuesta, reverse("mayoristas:mi_solicitud"))

    def test_un_administrador_no_registra_solicitud(self):
        admin = crear_usuario("adm", rol="ADMIN")
        self.client.force_login(admin)

        respuesta = self.client.get(self.url)

        self.assertRedirects(respuesta, reverse("usuarios:perfil"))

    def test_el_metodo_no_permitido_devuelve_405(self):
        self.client.force_login(crear_usuario("cli5"))
        self.assertEqual(self.client.put(self.url).status_code, 405)


class MiSolicitudTests(TestCase):
    """La deuda del día 1: quien acaba de solicitar NO puede recibir un 404."""

    def setUp(self):
        self.url = reverse("mayoristas:mi_solicitud")

    def test_cliente_con_solicitud_pendiente_recibe_200(self):
        usuario = crear_usuario("p1")
        registrar_solicitud(usuario, DATOS)
        self.client.force_login(usuario)

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Pendiente de aprobación")
        self.assertContains(respuesta, "Joyería Aurora")

    def test_muestra_el_motivo_cuando_fue_rechazada(self):
        usuario = crear_usuario("p2")
        s = registrar_solicitud(usuario, DATOS)
        s.estado = SolicitudMayorista.Estado.RECHAZADA
        s.motivo_rechazo = "El NIT no coincide con la Cámara de Comercio."
        s.save()
        self.client.force_login(usuario)

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, "No pudimos aprobar esta solicitud")
        self.assertContains(respuesta, "Cámara de Comercio")
        self.assertContains(respuesta, reverse("mayoristas:solicitar_acceso"))

    def test_sin_solicitud_invita_a_solicitar(self):
        self.client.force_login(crear_usuario("p3"))
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Todavía no has enviado una solicitud")

    def test_anonimo_va_al_login(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)

    def test_solo_muestra_la_solicitud_propia(self):
        """Acceso horizontal: cada quien ve la suya, no la del vecino."""
        ana = crear_usuario("ana7")
        luis = crear_usuario("luis7")
        registrar_solicitud(ana, {**DATOS, "nombre_comercial": "Aurora"})
        registrar_solicitud(
            luis, {**DATOS, "nit": "800111222", "nombre_comercial": "Lucero"}
        )
        self.client.force_login(luis)

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, "Lucero")
        self.assertNotContains(respuesta, "Aurora")

    def test_el_estado_no_se_cambia_por_get(self):
        """VM-01 no transiciona estados: eso es VM-02 y solo por POST."""
        usuario = crear_usuario("p4")
        s = registrar_solicitud(usuario, DATOS)
        self.client.force_login(usuario)

        self.client.get(self.url)

        s.refresh_from_db()
        self.assertEqual(s.estado, SolicitudMayorista.Estado.PENDIENTE)


class EnlacesDelSitioTests(TestCase):
    """El acceso a la solicitud debe ser encontrable, no una URL secreta."""

    def test_el_home_ofrece_el_acceso_mayorista(self):
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertContains(respuesta, reverse("mayoristas:solicitar_acceso"))

    def test_anonimo_es_enviado_al_login_con_retorno(self):
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertContains(
            respuesta,
            f"{reverse('core:iniciar_sesion')}?next={reverse('mayoristas:solicitar_acceso')}",
        )