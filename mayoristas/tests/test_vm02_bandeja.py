"""Pruebas de VM-02 (JODS-96): bandeja, decisión y notificación.

Se agrupan por capa, igual que las de VM-01:

  1. Servicio — las reglas de la transición (estado, rol, motivo).
  2. Notificación — a quién se escribe y qué pasa si el correo falla.
  3. Permisos — quién entra a la bandeja y quién puede decidir (Q-03/DEC-07).
  4. Vistas — GET/POST, 405, 404, CSRF y flujo completo.
  5. Regresión de VM-01 — aprobar no rompe la consulta del cliente.

Nada de esto toca la base de datos de desarrollo: `TestCase` crea una
temporal y la destruye al final.

El correo se prueba con el backend de memoria (`locmem`), que es el que usa
Django durante las pruebas: nada sale a la red y `mail.outbox` guarda lo
enviado. `transaction.on_commit` NO dispara sus callbacks dentro de un
`TestCase` (la transacción nunca se confirma), así que las clases que
comprueban el envío se marcan con `capturar_correo`, que cambia
`on_commit` por una llamada inmediata.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from mayoristas.models import SolicitudMayorista
from mayoristas.servicios import (
    aprobar_solicitud,
    rechazar_solicitud,
    registrar_solicitud,
)

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

PERMISO_VER = "mayoristas.ver_bandeja_solicitudesmayoristas"
PERMISO_GESTIONAR = "mayoristas.gestionar_solicitudesmayoristas"


def crear_usuario(nombre, **extra):
    return Usuario.objects.create_user(
        username=nombre,
        email=f"{nombre}@ejemplo.com",
        password="Clave-segura-123",
        **extra,
    )


def crear_revisor(nombre="revisor", con_ver=True, con_gestionar=True):
    """Cuenta NORMAL (no staff) con los permisos del módulo, como en Q-03."""
    usuario = crear_usuario(nombre)
    codenames = []
    if con_ver:
        codenames.append(PERMISO_VER)
    if con_gestionar:
        codenames.append(PERMISO_GESTIONAR)
    if codenames:
        usuario.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="mayoristas", codename__in=[
                    c.split(".", 1)[1] for c in codenames
                ]
            )
        )
    return Usuario.objects.get(pk=usuario.pk)


def capturar_correo():
    """Ejecuta `on_commit` en el acto para poder mirar `mail.outbox`.

    En un `TestCase` la transacción exterior nunca se confirma, así que los
    callbacks diferidos no corren y `mail.outbox` quedaría vacío. Esto NO
    cambia la lógica del servicio: la prueba `test_el_envio_esta_diferido_a_que_la_transaccion_confirme`
    comprueba que el envío está, de hecho, diferido.
    """
    return mock.patch(
        "mayoristas.servicios.transaction.on_commit",
        side_effect=lambda funcion, using=None: funcion(),
    )


def crear_solicitud(autor=None, **cambios):
    autor = autor or crear_usuario("solicitante")
    return registrar_solicitud(autor, {**DATOS, **cambios})


# ─────────────────────────────────────────────────────────────────────
# 1. Servicio: reglas de la transición
# ─────────────────────────────────────────────────────────────────────

class AprobarTests(TestCase):
    def setUp(self):
        self.solicitud = crear_solicitud()
        self.revisor = crear_revisor()

    def test_aprueba_y_otorga_rol_mayorista(self):
        aprobar_solicitud(self.solicitud, revisor=self.revisor)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "APROBADA")
        self.solicitud.usuario.refresh_from_db()
        self.assertEqual(self.solicitud.usuario.rol, "MAYORISTA")

    def test_registra_quien_revisa_y_cuando(self):
        antes = self.solicitud.revisado_en
        aprobar_solicitud(self.solicitud, revisor=self.revisor)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.revisado_por, self.revisor)
        self.assertIsNotNone(self.solicitud.revisado_en)
        self.assertNotEqual(self.solicitud.revisado_en, antes)

    def test_no_reaprueba_una_aprobada(self):
        """DEC-08: una decisión tomada no se repite."""
        aprobar_solicitud(self.solicitud, revisor=self.revisor)
        with self.assertRaises(ValidationError):
            aprobar_solicitud(self.solicitud, revisor=self.revisor)

    def test_no_aprueba_una_rechazada(self):
        rechazar_solicitud(self.solicitud, revisor=self.revisor, motivo="Falta RUT")
        with self.assertRaises(ValidationError):
            aprobar_solicitud(self.solicitud, revisor=self.revisor)

    def test_no_toca_is_staff_ni_is_superuser(self):
        """DEC-07: aprobar jamás convierte a nadie en personal ni admin."""
        aprobar_solicitud(self.solicitud, revisor=self.revisor)
        u = Usuario.objects.get(pk=self.solicitud.usuario.pk)
        self.assertFalse(u.is_staff)
        self.assertFalse(u.is_superuser)

    def test_a_un_administrador_no_le_cambia_el_rol(self):
        admin = crear_usuario("jefe", rol="ADMIN")
        solicitud = crear_solicitud(autor=admin, nit="700111222")
        aprobar_solicitud(solicitud, revisor=self.revisor)
        admin.refresh_from_db()
        self.assertEqual(admin.rol, "ADMIN")

    def test_dos_aprobaciones_simultaneas_solo_dejan_una_ganadora(self):
        """La segunda lectura ve el estado ya cambiado y no lo pisa."""
        aprobar_solicitud(self.solicitud, revisor=self.revisor)
        otra_instancia = SolicitudMayorista.objects.get(pk=self.solicitud.pk)
        with self.assertRaises(ValidationError):
            aprobar_solicitud(otra_instancia, revisor=self.revisor)


class RechazarTests(TestCase):
    def setUp(self):
        self.solicitud = crear_solicitud()
        self.revisor = crear_revisor()

    def test_rechaza_con_motivo_y_no_cambia_el_rol(self):
        rechazar_solicitud(self.solicitud, revisor=self.revisor, motivo="Falta RUT")
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "RECHAZADA")
        self.assertEqual(self.solicitud.motivo_rechazo, "Falta RUT")
        self.solicitud.usuario.refresh_from_db()
        self.assertEqual(self.solicitud.usuario.rol, "CLIENTE")

    def test_el_motivo_es_obligatorio(self):
        for vacio in ("", "   ", None):
            with self.assertRaises(ValidationError):
                rechazar_solicitud(self.solicitud, revisor=self.revisor, motivo=vacio)

    def test_guarda_el_motivo_sin_espacios_sobrantes(self):
        rechazar_solicitud(
            self.solicitud, revisor=self.revisor, motivo="  Falta el RUT  "
        )
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.motivo_rechazo, "Falta el RUT")

    def test_no_rechaza_una_aprobada(self):
        aprobar_solicitud(self.solicitud, revisor=self.revisor)
        with self.assertRaises(ValidationError):
            rechazar_solicitud(self.solicitud, revisor=self.revisor, motivo="X")

    def test_el_rechazo_libera_nit_y_cuenta(self):
        """DEC-08: el cliente puede volver a solicitar tras un rechazo."""
        rechazar_solicitud(self.solicitud, revisor=self.revisor, motivo="Falta RUT")
        nueva = crear_solicitud(
            autor=self.solicitud.usuario, nit="900.123.456-7"
        )
        self.assertEqual(nueva.estado, "PENDIENTE")

    def test_aprobar_limpia_un_motivo_anterior(self):
        """Si se rechazó y luego se aprobó otra, el motivo viejo no se arrastra."""
        rechazar_solicitud(self.solicitud, revisor=self.revisor, motivo="Falta RUT")
        nueva = crear_solicitud(autor=self.solicitud.usuario, nit="900.123.456-7")
        aprobar_solicitud(nueva, revisor=self.revisor)
        nueva.refresh_from_db()
        self.assertEqual(nueva.motivo_rechazo, "")


# ─────────────────────────────────────────────────────────────────────
# 2. Notificación (DEC-13 / Q-04)
# ─────────────────────────────────────────────────────────────────────

class NotificacionTests(TestCase):
    def setUp(self):
        self.solicitud = crear_solicitud()
        self.revisor = crear_revisor()
        self._correo = capturar_correo()
        self._correo.start()
        self.addCleanup(self._correo.stop)

    def test_la_aprobacion_manda_correo_a_la_cuenta(self):
        aprobar_solicitud(self.solicitud, revisor=self.revisor)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.solicitud.usuario.email])

    def test_el_correo_no_va_al_correo_de_contacto_del_formulario(self):
        """DEC-13: el del formulario es «de contacto», no el de la cuenta."""
        self.assertNotEqual(
            self.solicitud.correo, self.solicitud.usuario.email
        )
        aprobar_solicitud(self.solicitud, revisor=self.revisor)
        self.assertIn(self.solicitud.usuario.email, mail.outbox[0].to)
        self.assertNotIn(self.solicitud.correo, mail.outbox[0].to)

    def test_el_correo_de_rechazo_lleva_el_motivo(self):
        rechazar_solicitud(
            self.solicitud, revisor=self.revisor, motivo="El RUT está vencido"
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("El RUT está vencido", mail.outbox[0].body)

    def test_no_avisa_al_administrador(self):
        """Q-04: no hay notificación automática al administrador."""
        aprobar_solicitud(self.solicitud, revisor=self.revisor)
        self.assertEqual(len(mail.outbox), 1)

    def test_un_fallo_de_correo_no_deshace_la_decision(self):
        with mock.patch(
            "mayoristas.servicios.send_mail", side_effect=Exception("SMTP caído")
        ):
            aprobar_solicitud(self.solicitud, revisor=self.revisor)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "APROBADA")

    def test_sin_correo_en_la_cuenta_no_se_rompe(self):
        Usuario.objects.filter(pk=self.solicitud.usuario.pk).update(email="")
        aprobar_solicitud(self.solicitud, revisor=self.revisor)
        self.assertEqual(len(mail.outbox), 0)

    def test_el_envio_esta_diferido_a_que_la_transaccion_confirme(self):
        """El correo NO se manda dentro de la transacción.

        Se espía `on_commit` sin ejecutarlo: si el servicio enviara el correo
        directamente, `mail.outbox` tendría un mensaje aunque la transacción
        todavía pudiera deshacerse.
        """
        self._correo.stop()  # sin disparar el callback: nada debe salir
        with mock.patch("mayoristas.servicios.transaction.on_commit") as diferido:
            aprobar_solicitud(self.solicitud, revisor=self.revisor)

        diferido.assert_called_once()
        self.assertEqual(len(mail.outbox), 0)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "APROBADA")


# ─────────────────────────────────────────────────────────────────────
# 3. Permisos (Q-03 / DEC-07)
# ─────────────────────────────────────────────────────────────────────

class PermisosTests(TestCase):
    def setUp(self):
        self.solicitud = crear_solicitud()

    def test_los_permisos_existen_con_esos_codenames(self):
        existentes = set(
            Permission.objects.filter(
                content_type__app_label="mayoristas"
            ).values_list("codename", flat=True)
        )
        self.assertIn("ver_bandeja_solicitudesmayoristas", existentes)
        self.assertIn("gestionar_solicitudesmayoristas", existentes)

    def test_no_se_conceden_permisos_administrativos_generales(self):
        """Q-03: el permiso del módulo no es un pase al panel de administración."""
        revisor = crear_revisor("solo-ver", con_gestionar=False)
        self.assertFalse(revisor.has_perm("core.change_producto"))
        self.assertFalse(revisor.has_perm("auth.change_group"))
        self.assertTrue(revisor.has_perm(PERMISO_VER))
        self.assertFalse(revisor.has_perm(PERMISO_GESTIONAR))

    def test_anonimo_va_al_login(self):
        respuesta = self.client.get(reverse("mayoristas:bandeja"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login/", respuesta["Location"])

    def test_cliente_sin_permiso_recibe_403(self):
        self.client.force_login(crear_usuario("curioso"))
        respuesta = self.client.get(reverse("mayoristas:bandeja"))
        self.assertEqual(respuesta.status_code, 403)

    def test_quien_solo_ve_entra_pero_no_puede_decidir(self):
        solo_ver = crear_revisor("solo-ver", con_gestionar=False)
        self.client.force_login(solo_ver)

        bandeja = self.client.get(reverse("mayoristas:bandeja"))
        self.assertEqual(bandeja.status_code, 200)
        self.assertFalse(bandeja.context["puede_gestionar"])

        ficha = self.client.get(
            reverse("mayoristas:revision", args=[self.solicitud.pk])
        )
        self.assertEqual(ficha.status_code, 200)
        self.assertFalse(ficha.context["puede_decidir"])

    def test_quien_solo_ve_no_puede_aprobar_por_post(self):
        """El backend manda: fabricar el POST a mano no sirve de nada."""
        solo_ver = crear_revisor("solo-ver", con_gestionar=False)
        self.client.force_login(solo_ver)

        respuesta = self.client.post(
            reverse("mayoristas:aprobar", args=[self.solicitud.pk])
        )
        self.assertEqual(respuesta.status_code, 403)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "PENDIENTE")

    def test_quien_solo_ve_no_puede_rechazar_por_post(self):
        solo_ver = crear_revisor("solo-ver", con_gestionar=False)
        self.client.force_login(solo_ver)

        respuesta = self.client.post(
            reverse("mayoristas:rechazar", args=[self.solicitud.pk]),
            {"motivo": "X"},
        )
        self.assertEqual(respuesta.status_code, 403)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "PENDIENTE")


# ─────────────────────────────────────────────────────────────────────
# 4. Vistas
# ─────────────────────────────────────────────────────────────────────

class BandejaVistaTests(TestCase):
    def setUp(self):
        self.revisor = crear_revisor()
        self.client.force_login(self.revisor)
        self.pendiente = crear_solicitud(
            autor=crear_usuario("ana"), nit="900111222"
        )
        # Datos de contacto distintos a propósito: `DATOS` se comparte entre
        # pruebas y, si se deja el mismo correo, una búsqueda por «Aurora»
        # encontraría también esta solicitud.
        self.aprobada = crear_solicitud(
            autor=crear_usuario("luis"),
            nit="900333444",
            nombre_comercial="Distribuidora Andina",
            ciudad="Medellín",
            correo="andina@ejemplo.com",
        )
        aprobar_solicitud(self.aprobada, revisor=crear_revisor("otro"))

    def test_lista_todas_por_defecto(self):
        respuesta = self.client.get(reverse("mayoristas:bandeja"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context["solicitudes"]), 2)
        self.assertEqual(respuesta.context["resumen"]["TODAS"], 2)

    def test_el_resumen_cuenta_cada_estado(self):
        respuesta = self.client.get(reverse("mayoristas:bandeja"))
        resumen = respuesta.context["resumen"]
        self.assertEqual(resumen["PENDIENTE"], 1)
        self.assertEqual(resumen["APROBADA"], 1)
        self.assertEqual(resumen["RECHAZADA"], 0)

    def test_filtra_por_estado(self):
        respuesta = self.client.get(
            reverse("mayoristas:bandeja"), {"estado": "PENDIENTE"}
        )
        self.assertEqual(len(respuesta.context["solicitudes"]), 1)
        self.assertEqual(respuesta.context["solicitudes"][0], self.pendiente)

    def test_un_estado_inventado_no_filtra_ni_rompe(self):
        respuesta = self.client.get(
            reverse("mayoristas:bandeja"), {"estado": "BORRADO"}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["estado_filtro"], "")
        self.assertEqual(len(respuesta.context["solicitudes"]), 2)

    def test_busca_por_nombre_nit_ciudad_y_correo(self):
        casos = {
            "Aurora": self.pendiente,
            "900111222": self.pendiente,
            "Bogotá": self.pendiente,
            "ana@ejemplo.com": self.pendiente,
        }
        for texto, esperado in casos.items():
            respuesta = self.client.get(
                reverse("mayoristas:bandeja"), {"q": texto}
            )
            encontrados = list(respuesta.context["solicitudes"])
            self.assertEqual(encontrados, [esperado], texto)

    def test_busqueda_sin_resultados_muestra_estado_vacio(self):
        respuesta = self.client.get(
            reverse("mayoristas:bandeja"), {"q": "no-existe-1234"}
        )
        self.assertEqual(len(respuesta.context["solicitudes"]), 0)
        self.assertContains(respuesta, "No hay solicitudes que mostrar")

    def test_metodo_no_permitido_en_la_bandeja(self):
        respuesta = self.client.delete(reverse("mayoristas:bandeja"))
        self.assertEqual(respuesta.status_code, 405)


class FichaRevisionTests(TestCase):
    def setUp(self):
        self.revisor = crear_revisor()
        self.client.force_login(self.revisor)
        self.solicitud = crear_solicitud()

    def test_muestra_los_datos_declarados(self):
        respuesta = self.client.get(
            reverse("mayoristas:revision", args=[self.solicitud.pk])
        )
        self.assertContains(respuesta, "Joyería Aurora")
        self.assertContains(respuesta, "900123456-7")
        self.assertContains(respuesta, "Ana Pérez")

    def test_una_solicitud_inexistente_da_404(self):
        respuesta = self.client.get(reverse("mayoristas:revision", args=[999999]))
        self.assertEqual(respuesta.status_code, 404)

    def test_una_aprobada_no_ofrece_botones_de_decision(self):
        aprobar_solicitud(self.solicitud, revisor=self.revisor)
        respuesta = self.client.get(
            reverse("mayoristas:revision", args=[self.solicitud.pk])
        )
        self.assertFalse(respuesta.context["puede_decidir"])
        self.assertNotContains(respuesta, "Aprobar acceso")

    def test_la_ficha_ofrece_el_siguiente_de_la_cola(self):
        """Tras decidir se sigue con la siguiente sin volver a la bandeja."""
        otra = crear_solicitud(
            autor=crear_usuario("nuria"),
            nit="901222333",
            nombre_comercial="Otra Joyería",
            correo="nuria@ejemplo.com",
        )
        respuesta = self.client.get(
            reverse("mayoristas:revision", args=[self.solicitud.pk])
        )
        self.assertIn(otra, respuesta.context["solicitudes"])
        self.assertNotIn(self.solicitud, respuesta.context["solicitudes"])

    def test_la_cola_no_muestra_las_ya_decididas(self):
        aprobar_solicitud(self.solicitud, revisor=self.revisor)
        otra = crear_solicitud(
            autor=crear_usuario("nuria"), nit="901222333",
            nombre_comercial="Otra", correo="nuria@ejemplo.com",
        )
        respuesta = self.client.get(
            reverse("mayoristas:revision", args=[otra.pk])
        )
        self.assertNotIn(self.solicitud, respuesta.context["solicitudes"])

    def test_explica_que_no_se_repiten_las_decisiones(self):
        aprobar_solicitud(self.solicitud, revisor=self.revisor)
        respuesta = self.client.get(
            reverse("mayoristas:revision", args=[self.solicitud.pk])
        )
        self.assertContains(respuesta, "ya fue revisada")


class DecisionVistaTests(TestCase):
    def setUp(self):
        self.revisor = crear_revisor()
        self.client.force_login(self.revisor)
        self.solicitud = crear_solicitud()
        self._correo = capturar_correo()
        self._correo.start()
        self.addCleanup(self._correo.stop)

    def test_aprobar_por_post_funciona(self):
        respuesta = self.client.post(
            reverse("mayoristas:aprobar", args=[self.solicitud.pk])
        )
        self.assertRedirects(
            respuesta,
            reverse("mayoristas:revision", args=[self.solicitud.pk]),
        )
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "APROBADA")

    def test_aprobar_por_get_da_405(self):
        """DEC-06: un enlace no aprueba a nadie."""
        respuesta = self.client.get(
            reverse("mayoristas:aprobar", args=[self.solicitud.pk])
        )
        self.assertEqual(respuesta.status_code, 405)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "PENDIENTE")

    def test_rechazar_por_get_da_405(self):
        respuesta = self.client.get(
            reverse("mayoristas:rechazar", args=[self.solicitud.pk])
        )
        self.assertEqual(respuesta.status_code, 405)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "PENDIENTE")

    def test_put_y_delete_dan_405(self):
        for metodo in ("put", "patch", "delete"):
            respuesta = getattr(self.client, metodo)(
                reverse("mayoristas:aprobar", args=[self.solicitud.pk])
            )
            self.assertEqual(respuesta.status_code, 405, metodo)

    def test_rechazar_sin_motivo_vuelve_a_la_ficha_con_error(self):
        respuesta = self.client.post(
            reverse("mayoristas:rechazar", args=[self.solicitud.pk]),
            {"motivo": ""},
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertTrue(respuesta.context["form_rechazo"].errors)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "PENDIENTE")

    def test_rechazar_con_motivo_funciona(self):
        respuesta = self.client.post(
            reverse("mayoristas:rechazar", args=[self.solicitud.pk]),
            {"motivo": "El RUT no coincide con el NIT"},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "RECHAZADA")
        self.assertEqual(self.solicitud.motivo_rechazo, "El RUT no coincide con el NIT")

    def test_decidir_una_solicitud_ya_decidida_no_rompe(self):
        """Doble clic o pestaña vieja: mensaje, no error 500."""
        aprobar_solicitud(self.solicitud, revisor=self.revisor)
        respuesta = self.client.post(
            reverse("mayoristas:aprobar", args=[self.solicitud.pk])
        )
        self.assertEqual(respuesta.status_code, 302)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "APROBADA")

    def test_el_csrf_esta_activo_en_las_acciones(self):
        cliente_sin_csrf = self.client_class(enforce_csrf_checks=True)
        cliente_sin_csrf.force_login(self.revisor)
        respuesta = cliente_sin_csrf.post(
            reverse("mayoristas:aprobar", args=[self.solicitud.pk])
        )
        self.assertEqual(respuesta.status_code, 403)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "PENDIENTE")

    def test_aprobar_envia_un_solo_correo(self):
        self.client.post(reverse("mayoristas:aprobar", args=[self.solicitud.pk]))
        self.assertEqual(len(mail.outbox), 1)


# ─────────────────────────────────────────────────────────────────────
# 5. Regresión: el cliente ve el resultado (VM-01 ↔ VM-02)
# ─────────────────────────────────────────────────────────────────────

class ElClienteVeElResultadoTests(TestCase):
    def setUp(self):
        self.solicitud = crear_solicitud()
        self.cliente = self.solicitud.usuario

    def test_tras_aprobar_el_cliente_ve_aprobada(self):
        aprobar_solicitud(self.solicitud, revisor=crear_revisor())
        self.client.force_login(self.cliente)
        respuesta = self.client.get(reverse("mayoristas:mi_solicitud"))
        self.assertContains(respuesta, "Aprobada")
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.rol, "MAYORISTA")

    def test_tras_rechazar_el_cliente_ve_el_motivo(self):
        rechazar_solicitud(
            self.solicitud, revisor=crear_revisor(), motivo="Falta Cámara de Comercio"
        )
        self.client.force_login(self.cliente)
        respuesta = self.client.get(reverse("mayoristas:mi_solicitud"))
        self.assertContains(respuesta, "Falta Cámara de Comercio")
        self.assertContains(respuesta, "Volver a solicitar")

    def test_un_mayorista_ya_no_entra_al_formulario(self):
        aprobar_solicitud(self.solicitud, revisor=crear_revisor())
        self.client.force_login(self.cliente)
        respuesta = self.client.get(reverse("mayoristas:solicitar_acceso"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/mayoristas/solicitud/", respuesta["Location"])


# ─────────────────────────────────────────────────────────────────────
# 6. Admin de Django (complementario, no la bandeja)
# ─────────────────────────────────────────────────────────────────────

class AdminTests(TestCase):
    def test_el_estado_no_es_editable_desde_el_admin(self):
        """La decisión se toma en la bandeja, donde se avisa al cliente."""
        from django.contrib import admin

        from mayoristas.admin import SolicitudMayoristaAdmin

        modelo_admin = SolicitudMayoristaAdmin(SolicitudMayorista, admin.site)
        for campo in ("estado", "motivo_rechazo", "revisado_por", "revisado_en"):
            self.assertIn(campo, modelo_admin.readonly_fields)

    def test_no_se_crean_solicitudes_desde_el_admin(self):
        from django.contrib import admin

        from mayoristas.admin import SolicitudMayoristaAdmin

        modelo_admin = SolicitudMayoristaAdmin(SolicitudMayorista, admin.site)
        self.assertFalse(modelo_admin.has_add_permission(None))
