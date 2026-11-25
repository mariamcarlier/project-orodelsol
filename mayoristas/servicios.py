"""Servicio de registro de solicitudes de acceso mayorista (VM-01, JODS-95).

Capa de servicios: la vista no construye modelos ni decide reglas. Aquí se
concentra la regla de negocio del registro y la transacción.

La normalización del NIT **no** vive aquí: vive en el modelo, para que también
la apliquen el panel de Django y el ORM directo. Este servicio no duplica esa
lógica; solo garantiza que la validación y el guardado ocurran en una sola
transacción.
"""

import logging

from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import SolicitudMayorista

logger = logging.getLogger(__name__)

# Campos que el servicio acepta del formulario. Es una lista blanca: cualquier
# otro dato (`estado`, `motivo_rechazo`, `usuario`…) se descarta en silencio,
# de modo que nadie puede autoaprobarse enviando campos extra.
CAMPOS_FORMULARIO = (
    "tipo_persona",
    "nit",
    "nombre_comercial",
    "representante_legal",
    "ciudad",
    "telefono",
    "correo",
    "canal_venta",
    "referido",
)


@transaction.atomic
def registrar_solicitud(usuario, datos):
    """Crea una solicitud en estado PENDIENTE para `usuario`.

    Args:
        usuario: instancia de `Usuario` ya autenticada.
        datos: diccionario con los campos de `CAMPOS_FORMULARIO`.

    Returns:
        La `SolicitudMayorista` guardada, siempre en estado PENDIENTE.

    Raises:
        ValidationError: si el usuario ya tiene una solicitud activa, si el
            NIT ya está ocupado por otra solicitud activa, o si algún campo no
            cumple su formato. Los mensajes son los que se muestran en pantalla.
    """
    limpios = {c: datos[c] for c in CAMPOS_FORMULARIO if c in datos}
    solicitud = SolicitudMayorista(usuario=usuario, **limpios)

    # Comprobaciones de negocio ANTES de tocar la base de datos: dan un
    # mensaje legible en lugar de un IntegrityError. La restricción de la
    # base de datos sigue estando detrás como última barrera.
    activas = SolicitudMayorista.objects.activas()
    if activas.filter(usuario=usuario).exists():
        raise ValidationError("Ya tienes una solicitud en curso o aprobada.")
    if activas.filter(nit=solicitud.nit).exists():
        raise ValidationError("Ya existe una solicitud con este NIT o cédula.")

    solicitud.full_clean()
    try:
        solicitud.save()
    except IntegrityError as exc:
        # Dos envíos simultáneos del mismo NIT pueden pasar las dos
        # comprobaciones anteriores y chocar en la restricción única.
        raise ValidationError(
            "Ya existe una solicitud con este NIT o cédula."
        ) from exc
    return solicitud


# ═══════════════════════════════════════════════════════════════════════
# VM-02 (JODS-96) · Verificación y decisión de la solicitud
# ═══════════════════════════════════════════════════════════════════════
#
# Toda transición de estado pasa por aquí. La vista comprueba permisos; el
# servicio comprueba la REGLA. Si mañana el estado se cambia desde un comando
# o desde una integración, la regla se sigue cumpliendo.
#
# Concurrencia: se relee la fila con `select_for_update()` dentro de la
# transacción. Sin ese bloqueo, dos personas con permiso pulsando «Aprobar» a
# la vez leerían PENDIENTE las dos y la segunda sobrescribiría a la primera.

ESTADOS_QUE_PERMITEN_DECISION = (SolicitudMayorista.Estado.PENDIENTE,)


def _solicitud_bloqueada(solicitud):
    """Relee la solicitud con bloqueo de fila dentro de la transacción abierta."""
    return (
        SolicitudMayorista.objects.select_for_update()
        .select_related("usuario")
        .get(pk=solicitud.pk)
    )


def _exigir_pendiente(solicitud):
    """DEC-08: una solicitud ya decidida no se vuelve a decidir."""
    if solicitud.estado != SolicitudMayorista.Estado.PENDIENTE:
        raise ValidationError(
            "Esta solicitud ya fue revisada. Recarga la página para ver su estado actual."
        )


@transaction.atomic
def aprobar_solicitud(solicitud, revisor):
    """Aprueba la solicitud y otorga el rol MAYORISTA a su autor.

    Reglas que aplica:

    - Solo se aprueba lo que está PENDIENTE (DEC-08).
    - El rol solo sube de CLIENTE a MAYORISTA. Si la cuenta es de
      administración, no se le cambia el rol: un administrador no necesita
      acceso mayorista y no se le debe alterar la cuenta. Tampoco se tocan
      `is_staff` ni `is_superuser` (DEC-07).
    - El correo sale al terminar la transacción, no antes: si el guardado
      falla, no se manda un aviso de una aprobación que no existió.

    Args:
        solicitud: la `SolicitudMayorista` a aprobar.
        revisor: usuario que decide; queda registrado en `revisado_por`.

    Returns:
        La solicitud recargada y ya aprobada.

    Raises:
        ValidationError: si la solicitud no está pendiente.
    """
    bloqueada = _solicitud_bloqueada(solicitud)
    _exigir_pendiente(bloqueada)

    bloqueada.estado = SolicitudMayorista.Estado.APROBADA
    bloqueada.motivo_rechazo = ""
    bloqueada.revisado_por = revisor
    bloqueada.revisado_en = timezone.now()
    bloqueada.save(
        update_fields=["estado", "motivo_rechazo", "revisado_por", "revisado_en"]
    )

    usuario = bloqueada.usuario
    if usuario.rol == "CLIENTE" and not usuario.es_administrador:
        usuario.rol = "MAYORISTA"
        usuario.save(update_fields=["rol"])

    transaction.on_commit(lambda: notificar_decision(bloqueada))
    return bloqueada


@transaction.atomic
def rechazar_solicitud(solicitud, revisor, motivo):
    """Rechaza la solicitud con un motivo obligatorio.

    El motivo es obligatorio porque es lo único que el cliente recibe para
    saber qué corregir; sin él, «rechazada» no le dice nada. Al rechazar, ni
    el usuario ni el NIT quedan ocupados: la restricción de unicidad solo
    cubre solicitudes activas, de modo que puede volver a solicitar (DEC-08).

    Raises:
        ValidationError: si la solicitud no está pendiente o el motivo está vacío.
    """
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError("Escribe el motivo del rechazo: el cliente lo verá.")

    bloqueada = _solicitud_bloqueada(solicitud)
    _exigir_pendiente(bloqueada)

    bloqueada.estado = SolicitudMayorista.Estado.RECHAZADA
    bloqueada.motivo_rechazo = motivo
    bloqueada.revisado_por = revisor
    bloqueada.revisado_en = timezone.now()
    bloqueada.save(
        update_fields=["estado", "motivo_rechazo", "revisado_por", "revisado_en"]
    )

    transaction.on_commit(lambda: notificar_decision(bloqueada))
    return bloqueada


def notificar_decision(solicitud):
    """Avisa al cliente del resultado (DEC-13).

    Se manda al correo de la CUENTA, no al «correo de contacto» que la persona
    escribió en el formulario: ese dato lo pudo escribir cualquiera y no está
    verificado, así que no sirve para avisar de una decisión sobre su cuenta.

    Nunca lanza: un fallo de SMTP no puede deshacer una aprobación ya
    guardada. El error se registra y la decisión queda tomada.
    """
    destinatario = (solicitud.usuario.email or "").strip()
    if not destinatario:
        logger.warning(
            "Solicitud %s decidida sin correo de cuenta: no se pudo notificar.",
            solicitud.pk,
        )
        return

    if solicitud.estado == SolicitudMayorista.Estado.APROBADA:
        asunto = "Tu acceso mayorista fue aprobado"
        mensaje = (
            f"Hola, {solicitud.usuario.nombre_visible}:\n\n"
            f"Revisamos la solicitud de {solicitud.nombre_comercial} y fue aprobada.\n"
            "Tu cuenta ya tiene el rol de mayorista.\n\n"
            "El catálogo mayorista con precios de referencia se habilita en la "
            "siguiente entrega; te avisaremos en cuanto esté disponible.\n\n"
            "Joyería Oro del Sol"
        )
    else:
        asunto = "Sobre tu solicitud de acceso mayorista"
        mensaje = (
            f"Hola, {solicitud.usuario.nombre_visible}:\n\n"
            f"Revisamos la solicitud de {solicitud.nombre_comercial} y por ahora "
            "no pudimos aprobarla.\n\n"
            f"Motivo: {solicitud.motivo_rechazo}\n\n"
            "Puedes corregir la información y volver a enviar tu solicitud "
            "cuando quieras.\n\n"
            "Joyería Oro del Sol"
        )

    try:
        send_mail(
            asunto,
            mensaje,
            None,  # usa DEFAULT_FROM_EMAIL
            [destinatario],
            fail_silently=False,
        )
    except Exception:  # noqa: BLE001 - el correo no puede tumbar la decisión
        logger.exception(
            "No se pudo enviar el correo de la solicitud %s a %s",
            solicitud.pk,
            destinatario,
        )


# ═══════════════════════════════════════════════════════════════════════
# VM-16 (JODS-110) · Precio de referencia con tramo
# ═══════════════════════════════════════════════════════════════════════
#
# DEC-18: sin porcentaje configurado NO se calcula. Este servicio devuelve
# ``None`` en ``precio_con_tramo`` y la plantilla enseña el aviso. No hay
# ningún valor por defecto escondido: si no hay cifra comercial, no hay cifra.


def precio_con_tramo(precio_base, cantidad):
    """Aplica el tramo que corresponde a `cantidad` sobre `precio_base`.

    Args:
        precio_base: `Decimal` con el precio unitario (ya sea el «Desde» del
            catálogo o el de una línea de cotización).
        cantidad: unidades. Nunca se inventa un tramo para cantidades fuera
            de rango.

    Returns:
        dict con:
          - ``tramo``: el `TramoPrecioReferencia` aplicado, o None.
          - ``porcentaje``: el porcentaje aplicado, o None.
          - ``precio_unitario``: precio con el descuento, o el base si no hay
            tramo.
          - ``total``: ``precio_unitario × cantidad``.
          - ``calculado``: False si no había tramo configurado (DEC-18).

    No guarda nada ni toca la base de datos más allá de leer los tramos.
    """
    from decimal import Decimal, ROUND_HALF_UP

    from . import selectors

    precio_base = Decimal(precio_base or 0)
    cantidad = int(cantidad or 0)
    tramo = selectors.tramo_para_cantidad(cantidad)

    if tramo is None or tramo.porcentaje is None:
        return {
            "tramo": None,
            "porcentaje": None,
            "precio_unitario": precio_base,
            "total": (precio_base * cantidad).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            "calculado": False,
        }

    factor = (Decimal("100") - tramo.porcentaje) / Decimal("100")
    unitario = (precio_base * factor).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return {
        "tramo": tramo,
        "porcentaje": tramo.porcentaje,
        "precio_unitario": unitario,
        "total": (unitario * cantidad).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        "calculado": True,
    }
