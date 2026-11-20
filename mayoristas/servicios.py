"""Servicio de registro de solicitudes de acceso mayorista (VM-01, JODS-95).

Capa de servicios: la vista no construye modelos ni decide reglas. Aquí se
concentra la regla de negocio del registro y la transacción.

La normalización del NIT **no** vive aquí: vive en el modelo, para que también
la apliquen el panel de Django y el ORM directo. Este servicio no duplica esa
lógica; solo garantiza que la validación y el guardado ocurran en una sola
transacción.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import SolicitudMayorista

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
