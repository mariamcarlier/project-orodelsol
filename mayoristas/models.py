""" Modelos del canal B2B (épica Gestión de Mayoristas, JODS-6).

`SolicitudMayorista` guarda el registro extendido de una joyería o distribuidor que pide acceso al catálogo mayorista (VM-01, JODS-95).

Reglas que este archivo hace cumplir, y dónde:

- **El estado inicial es siempre PENDIENTE.** Es el `default` del campo y el servicio de registro ignora lo que llegue de fuera.
- **Unicidad condicional, no global.** El NIT es único *solo* entre solicitudes activas (PENDIENTE o APROBADA). Una solicitud RECHAZADA no bloquea: es justo lo que permite volver a solicitar tras un rechazo.
- **El NIT se guarda normalizado.** Se acepta escrito con puntos y espacios ("900.123.456-7") pero se persiste canónico ("900123456-7"). Sin esto, el mismo NIT escrito de dos formas pasaría la restricción de unicidad dos veces. La normalización vive en el MODELO, no solo en el servicio, porque el ORM (`objects.create`) y el panel de Django no pasan por el servicio.
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
        # Permisos propios (Q-03). NO se reutilizan los permisos automáticos
        # `change_solicitudmayorista`, porque tendrían el mismo efecto que
        # editar cualquier campo a mano y no distinguen «mirar» de «decidir».
        # Se asignan por grupo de Django: no se crea un rol nuevo (DEC-15) ni
        # se toca `is_staff` (DEC-07), así que quien revisa puede ser una
        # cuenta normal con este permiso y nada más.
        permissions = [
            (
                "ver_bandeja_solicitudesmayoristas",
                "Puede ver la bandeja de solicitudes de mayoristas",
            ),
            (
                "gestionar_solicitudesmayoristas",
                "Puede aprobar y rechazar solicitudes de mayoristas",
            ),
        ]
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


# ═══════════════════════════════════════════════════════════════════════
# VM-16 (JODS-110) · Tramos de precio de referencia
# ═══════════════════════════════════════════════════════════════════════
#
# DEC-02: los tramos (10–29, 30–59, 60+) SON CONFIGURABLES y viven en la base
# de datos. NO se siembra ningún porcentaje: el campo arranca en NULL y un
# administrador lo define desde el panel. Mientras no haya porcentaje, el
# sistema NO calcula nada y la pantalla lo dice (DEC-18).
#
# Por qué el porcentaje es NULL y no 0:
#   ``0`` es un valor comercial válido («sin descuento»). Si se usara 0 para
#   «no configurado», no habría forma de distinguir «este tramo no tiene
#   descuento» de «este tramo está sin definir», y el catálogo mostraría un
#   precio como si estuviera configurado cuando en realidad nadie lo decidió.


class TramoPrecioReferencia(models.Model):
    """Un rango de cantidad con su porcentaje de referencia (VM-16, JODS-110).

    El porcentaje es opcional a propósito: mientras esté en NULL, el tramo
    existe pero NO se aplica. Es la forma de que la estructura (los tres
    rangos que acordó el negocio) exista sin inventar cifras comerciales.
    """

    class Alcance(models.TextChoices):
        MAYORISTA = "MAYORISTA", "Mayorista"

    nombre = models.CharField(
        "nombre del tramo", max_length=60,
        help_text="Cómo lo verá el equipo en el panel, por ejemplo «Medio mayorista».",
    )
    cantidad_minima = models.PositiveIntegerField(
        "cantidad mínima",
        help_text="Desde cuántas unidades aplica el tramo.",
    )
    cantidad_maxima = models.PositiveIntegerField(
        "cantidad máxima", null=True, blank=True,
        help_text=(
            "Hasta cuántas unidades aplica. Déjalo vacío para «sin límite» "
            "(el tramo de 60 o más)."
        ),
    )
    porcentaje = models.DecimalField(
        "porcentaje de referencia",
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text=(
            "Porcentaje que se muestra como referencia sobre el precio. "
            "Déjalo vacío mientras no esté definido: sin porcentaje no se "
            "calcula nada y no se inventa ninguna cifra."
        ),
    )
    activo = models.BooleanField("activo", default=True)
    creado_en = models.DateTimeField("creado en", auto_now_add=True)

    class Meta:
        ordering = ("cantidad_minima",)
        verbose_name = "tramo de precio de referencia"
        verbose_name_plural = "tramos de precio de referencia"
        constraints = [
            models.CheckConstraint(
                condition=Q(cantidad_minima__gte=1),
                name="tramo_cantidad_minima_positiva",
            ),
            models.CheckConstraint(
                condition=Q(cantidad_maxima__isnull=True)
                | Q(cantidad_maxima__gte=models.F("cantidad_minima")),
                name="tramo_rango_coherente",
            ),
            models.CheckConstraint(
                condition=Q(porcentaje__isnull=True)
                | (Q(porcentaje__gte=0) & Q(porcentaje__lte=100)),
                name="tramo_porcentaje_valido",
            ),
        ]

    def __str__(self):
        rango = (
            f"{self.cantidad_minima}+"
            if self.cantidad_maxima is None
            else f"{self.cantidad_minima}–{self.cantidad_maxima}"
        )
        if self.porcentaje is None:
            return f"{self.nombre} ({rango}, sin porcentaje)"
        return f"{self.nombre} ({rango}, {self.porcentaje}%)"

    @property
    def configurado(self):
        """True si el tramo tiene un porcentaje definido y puede aplicarse."""
        return self.porcentaje is not None

    @property
    def rango_display(self):
        """Texto del rango para pantalla: «10 – 29» o «60 o más»."""
        if self.cantidad_maxima is None:
            return f"{self.cantidad_minima} o más"
        return f"{self.cantidad_minima} – {self.cantidad_maxima}"

    def clean(self):
        """Mensajes legibles; las restricciones de BD siguen detrás."""
        errores = {}
        if (
            self.cantidad_maxima is not None
            and self.cantidad_minima is not None
            and self.cantidad_maxima < self.cantidad_minima
        ):
            errores["cantidad_maxima"] = (
                "La cantidad máxima no puede ser menor que la mínima."
            )
        if self.porcentaje is not None and not (0 <= self.porcentaje <= 100):
            errores["porcentaje"] = "El porcentaje debe estar entre 0 y 100."
        if errores:
            raise ValidationError(errores)


# ═══════════════════════════════════════════════════════════════════════
# Días hábiles (RN-VM-06) · Calendario de festivos
# ═══════════════════════════════════════════════════════════════════════
# RN-VM-06 pide responder una cotización en 24–48 HORAS HÁBILES. «Hábil» no es «día de semana»: en Colombia hay festivos que caen en lunes y días que no cambian de fecha (Semana Santa). Por eso el cálculo necesita un calendario.

# Los festivos NO se escriben en el código: se guardan en la base de datos, porque cambian cada año y quien debe poder corregirlos es el administrador, no un programador. La tabla arranca VACÍA y el cálculo, sin festivos cargados, solo descuenta fines de semana: es el comportamiento correctopara un año sin calendario, y la pantalla lo indica.


class DiaNoHabil(models.Model):
    """Un día que no cuenta como hábil (festivo o cierre) (RN-VM-06).

    Solo los días que NO son sábado ni domingo necesitan estar aquí: el cálculo ya descuenta los fines de semana por su cuenta.
    """

    fecha = models.DateField("fecha", unique=True)
    nombre = models.CharField(
        "nombre", max_length=120,
        help_text="Por ejemplo «Día de la Independencia» o «Cierre por inventario».",
    )

    class Meta:
        ordering = ("fecha",)
        verbose_name = "día no hábil"
        verbose_name_plural = "días no hábiles"

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y} · {self.nombre}"

    def clean(self):
        """Un sábado o domingo no necesita registrarse: ya no es hábil."""
        if self.fecha and self.fecha.weekday() >= 5:
            raise ValidationError(
                {
                    "fecha": (
                        "Los sábados y domingos ya no cuentan como hábiles. "
                        "No hace falta registrarlos."
                    )
                }
            )