"""Selectores del canal B2B: SOLO lectura.

Un selector no escribe, no valida ni lanza reglas de negocio: devuelve datos
ya preparados para una vista. Así las consultas quedan en un único sitio y la
vista no arma querysets a mano.
"""

from django.db.models import Count, Q

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


# ═══════════════════════════════════════════════════════════════════════
# VM-02 (JODS-96) · Bandeja de verificación
# ═══════════════════════════════════════════════════════════════════════

ESTADOS_FILTRO = (
    SolicitudMayorista.Estado.PENDIENTE,
    SolicitudMayorista.Estado.APROBADA,
    SolicitudMayorista.Estado.RECHAZADA,
)


def bandeja_solicitudes(estado=None, busqueda=""):
    """Solicitudes para la bandeja de verificación, ya ordenadas.

    Args:
        estado: uno de los códigos de `ESTADOS_FILTRO`; cualquier otro valor o
            vacío devuelve todas.
        busqueda: texto libre que se compara con nombre comercial, NIT,
            ciudad y correo del solicitante. Los filtros se combinan con AND.

    Returns:
        QuerySet con `select_related("usuario")` y `revisado_por` precargados,
        para que la tabla no dispare una consulta por fila.
    """
    consulta = SolicitudMayorista.objects.select_related("usuario", "revisado_por")

    if estado in ESTADOS_FILTRO:
        consulta = consulta.filter(estado=estado)

    texto = (busqueda or "").strip()
    if texto:
        consulta = consulta.filter(
            Q(nombre_comercial__icontains=texto)
            | Q(nit__icontains=texto)
            | Q(ciudad__icontains=texto)
            | Q(correo__icontains=texto)
            | Q(usuario__email__icontains=texto)
        )

    return consulta


def resumen_bandeja():
    """Cuántas solicitudes hay en cada estado, para las pestañas de la bandeja.

    Un solo agregado en lugar de tres `count()`: la bandeja enseña siempre los
    tres números aunque esté filtrando por uno.
    """
    conteo = dict(
        SolicitudMayorista.objects.values_list("estado")
        .annotate(total=Count("pk"))
        .values_list("estado", "total")
    )
    resumen = {clave: conteo.get(clave, 0) for clave in ESTADOS_FILTRO}
    resumen["TODAS"] = sum(resumen.values())
    return resumen


def solicitud_para_revision(pk):
    """Una solicitud concreta con lo necesario para revisarla, o None.

    Devuelve None en lugar de lanzar `DoesNotExist`: la vista decide si eso es
    un 404. Se precargan usuario y revisor para no repetir consultas.
    """
    return (
        SolicitudMayorista.objects.select_related("usuario", "revisado_por")
        .filter(pk=pk)
        .first()
    )
