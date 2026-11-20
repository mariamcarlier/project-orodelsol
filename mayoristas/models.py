"""Modelos del canal B2B (épica Gestión de Mayoristas, JODS-6).

`SolicitudMayorista` guarda el registro extendido de una joyería o
distribuidor que pide acceso al catálogo mayorista (VM-01, JODS-95).

Reglas que este archivo hace cumplir, y dónde:

- **El estado inicial es siempre PENDIENTE.** Es el `default` del campo y el
  servicio de registro ignora lo que llegue de fuera.
- **Unicidad condicional, no global.** El NIT es único *solo* entre
  solicitudes activas (PENDIENTE o APROBADA). Una solicitud RECHAZADA no
  bloquea: es justo lo que permite volver a solicitar tras un rechazo.
- **El NIT se guarda normalizado.** Se acepta escrito con puntos y espacios
  ("900.123.456-7") pero se persiste canónico ("900123456-7"). Sin esto, el
  mismo NIT escrito de dos formas pasaría la restricción de unicidad dos
  veces. La normalización vive en el MODELO, no solo en el servicio, porque
  el ORM (`objects.create`) y el panel de Django no pasan por el servicio.
"""

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

ESTADOS_ACTIVOS = ("PENDIENTE", "APROBADA")

PATRON_NIT = re.compile(r"^\d{5,12}(-\d)?$")
MENSAJE_NIT = (
    "Escribe solo números; si tienes dígito de verificación, escríbelo con guion."
)


def normalizar_nit(valor):
    """Deja el NIT en su forma canónica: sin puntos ni espacios.

    "900.123.456-7" -> "900123456-7". El guion del dígito de verificación se
    conserva porque forma parte del número.
    """
    return re.sub(r"[\s.]", "", (valor or ""))


def validar_nit(valor):
    """Comprueba el formato del NIT YA normalizado.

    Se valida aparte del campo (y no con un `RegexValidator` del campo) para
    que la comprobación ocurra DESPUÉS de normalizar. Un validador de campo
    rechaza "900.123.456-7" antes de que se pueda limpiar.
    """
    if not PATRON_NIT.match(valor or ""):
        raise ValidationError({"nit": MENSAJE_NIT})


class SolicitudQuerySet(models.QuerySet):
    def activas(self):
        """Solicitudes que ocupan el NIT y el usuario: pendientes o aprobadas."""
        return self.filter(estado__in=ESTADOS_ACTIVOS)


class SolicitudMayorista(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de aprobación"
        APROBADA = "APROBADA", "Aprobada"
        RECHAZADA = "RECHAZADA", "Rechazada"

    class TipoPersona(models.TextChoices):
        NATURAL = "NATURAL", "Persona natural"
        EMPRESA = "EMPRESA", "Empresa"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="solicitudes_mayorista",
        verbose_name="usuario",
    )
    tipo_persona = models.CharField(
        max_length=10,
        choices=TipoPersona.choices,
        default=TipoPersona.EMPRESA,
        verbose_name="tipo de persona",
    )
    # Sin `RegexValidator` en el campo a propósito: se valida en
    # `clean_fields()`, después de normalizar (ver `validar_nit`).
    nit = models.CharField(
        "NIT o cédula",
        max_length=20,
        help_text="Solo números; si tiene dígito de verificación, con guion.",
    )
    nombre_comercial = models.CharField("nombre comercial", max_length=200)
    representante_legal = models.CharField("representante legal", max_length=200)
    ciudad = models.CharField("ciudad", max_length=100)
    telefono = models.CharField("teléfono", max_length=20)
    correo = models.EmailField("correo de contacto")
    canal_venta = models.CharField(
        "dónde vende", max_length=100, blank=True,
        help_text="Tienda física, redes sociales, ferias…",
    )
    referido = models.CharField(
        "referido por", max_length=200, blank=True,
        help_text="Persona o negocio que la recomendó, si aplica.",
    )

    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.PENDIENTE,
    )
    motivo_rechazo = models.TextField("motivo del rechazo", blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="solicitudes_revisadas",
        verbose_name="revisado por",
    )
    revisado_en = models.DateTimeField("revisado en", null=True, blank=True)
    creado_en = models.DateTimeField("creada en", auto_now_add=True)

    objects = SolicitudQuerySet.as_manager()

    class Meta:
        ordering = ("-creado_en",)
        verbose_name = "solicitud de mayorista"
        verbose_name_plural = "solicitudes de mayoristas"
        constraints = [
            models.UniqueConstraint(
                fields=["usuario"], condition=Q(estado__in=ESTADOS_ACTIVOS),
                name="mayoristas_una_activa_por_usuario",
            ),
            models.UniqueConstraint(
                fields=["nit"], condition=Q(estado__in=ESTADOS_ACTIVOS),
                name="mayoristas_nit_unico_en_activas",
            ),
        ]

    def clean_fields(self, exclude=None):
        """Normaliza el NIT antes de validar los campos.

        Django valida los campos (validadores) y después llama a `clean()`.
        Por eso la limpieza va aquí y no en `clean()`: cuando `clean()` se
        ejecuta, el error del validador ya se registró.

        Los errores se acumulan en lugar de cortarse en el primero, para que
        un formulario muestre de una vez todo lo que falta (por ejemplo, el
        NIT mal escrito *y* la ciudad vacía).
        """
        self.nit = normalizar_nit(self.nit)
        errores = {}
        try:
            validar_nit(self.nit)
        except ValidationError as exc:
            errores.update(exc.message_dict)
        try:
            super().clean_fields(exclude=exclude)
        except ValidationError as exc:
            # Los del NIT ya calculados tienen prioridad sobre los del campo.
            errores = {**exc.message_dict, **errores}
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        """Persiste siempre el NIT canónico, venga de donde venga el guardado.

        `objects.create()`, el panel de Django y las migraciones de datos no
        pasan por `clean_fields()`; sin esta línea, el NIT con puntos entraría
        a la base de datos y el `UniqueConstraint` no lo vería como duplicado.
        """
        self.nit = normalizar_nit(self.nit)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre_comercial} ({self.get_estado_display()})"
