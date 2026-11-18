from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

ESTADOS_ACTIVOS = ("PENDIENTE", "APROBADA")


class SolicitudQuerySet(models.QuerySet):
    def activas(self):
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
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="solicitudes_mayorista",
    )
    tipo_persona = models.CharField(
        max_length=10, choices=TipoPersona.choices, default=TipoPersona.EMPRESA)
    nit = models.CharField(
        "NIT o cédula", max_length=15,
        validators=[RegexValidator(
            r"^\d{5,12}(-\d)?$",
            "Escribe solo números; si tienes dígito de verificación, con guion.")],
    )
    nombre_comercial = models.CharField(max_length=200)
    representante_legal = models.CharField(max_length=200)
    ciudad = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)
    correo = models.EmailField()
    canal_venta = models.CharField(
        "Dónde vende", max_length=100, blank=True)
    referido = models.CharField(max_length=200, blank=True)

    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    motivo_rechazo = models.TextField(blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="solicitudes_revisadas")
    revisado_en = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    objects = SolicitudQuerySet.as_manager()

    class Meta:
        ordering = ("-creado_en",)
        verbose_name = "solicitud de mayorista"
        verbose_name_plural = "solicitudes de mayoristas"
        constraints = [
            models.UniqueConstraint(
                fields=["usuario"], condition=Q(estado__in=ESTADOS_ACTIVOS),
                name="mayoristas_una_activa_por_usuario"),
            models.UniqueConstraint(
                fields=["nit"], condition=Q(estado__in=ESTADOS_ACTIVOS),
                name="mayoristas_nit_unico_en_activas"),
        ]

    def __str__(self):
        return f"{self.nombre_comercial} ({self.get_estado_display()})"