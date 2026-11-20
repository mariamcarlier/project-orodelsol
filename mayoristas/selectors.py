"""Selectores del canal B2B: SOLO lectura.

Un selector no escribe, no valida ni lanza reglas de negocio: devuelve datos
ya preparados para una vista. Así las consultas quedan en un único sitio y la
vista no arma querysets a mano.
"""

from .models import SolicitudMayorista


def solicitud_activa_de(usuario):
    """Solicitud PENDIENTE o APROBADA del usuario, o None si no tiene.

    Es la consulta que decide si alguien puede volver a solicitar. Solo tiene
    sentido con un usuario autenticado.
    """
    if not getattr(usuario, "is_authenticated", False):
        return None
    return (
        SolicitudMayorista.objects.activas()
        .filter(usuario=usuario)
        .order_by("-creado_en")
        .first()
    )


def ultima_solicitud_de(usuario):
    """La solicitud más reciente del usuario, sea cual sea su estado.

    Es la que se muestra en «Estado de mi solicitud»: si la última fue
    rechazada, hay que poder enseñar el motivo y el enlace para volver a
    solicitar.
    """
    if not getattr(usuario, "is_authenticated", False):
        return None
    return (
        SolicitudMayorista.objects.filter(usuario=usuario)
        .order_by("-creado_en")
        .first()
    )


def puede_solicitar(usuario, solicitud=None):
    """Datos de decisión para la vista de solicitud, sin lógica duplicada.

    Devuelve un diccionario con:
      - ``puede``: si el formulario debe mostrarse.
      - ``motivo``: por qué no, con el texto que se enseña en pantalla.
      - ``solicitud``: la solicitud activa que bloquea, si la hay.

    Nota: **no** decide por rol. Que el rol sea o no CLIENTE se comprueba en la
    vista con `Usuario.rol_efectivo`, porque es una regla de acceso y no de
    datos.
    """
    activa = solicitud if solicitud is not None else solicitud_activa_de(usuario)
    if activa is None:
        return {"puede": True, "motivo": "", "solicitud": None}
    if activa.estado == SolicitudMayorista.Estado.PENDIENTE:
        motivo = "Tu solicitud está en revisión."
    else:
        motivo = "Tu acceso mayorista ya está aprobado."
    return {"puede": False, "motivo": motivo, "solicitud": activa}
