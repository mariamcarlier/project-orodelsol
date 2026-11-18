import re

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import SolicitudMayorista

CAMPOS_FORMULARIO = (
    "tipo_persona", "nit", "nombre_comercial", "representante_legal",
    "ciudad", "telefono", "correo", "canal_venta", "referido",
)


@transaction.atomic
def registrar_solicitud(usuario, datos):
    """Crea una solicitud PENDIENTE. Ignora cualquier campo fuera de la lista."""
    limpios = {c: datos[c] for c in CAMPOS_FORMULARIO if c in datos}
    limpios["nit"] = re.sub(r"[\s.]", "", limpios.get("nit", ""))

    activas = SolicitudMayorista.objects.activas()
    if activas.filter(usuario=usuario).exists():
        raise ValidationError("Ya tienes una solicitud en curso o aprobada.")
    if activas.filter(nit=limpios["nit"]).exists():
        raise ValidationError("Ya existe una solicitud con este NIT o cédula.")

    solicitud = SolicitudMayorista(usuario=usuario, **limpios)
    solicitud.full_clean()
    try:
        solicitud.save()
    except IntegrityError as exc:
        raise ValidationError("No se pudo registrar la solicitud.") from exc
    return solicitud