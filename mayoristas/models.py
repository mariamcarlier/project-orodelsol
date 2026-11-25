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

from .storage import almacenamiento_privado

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
@@ -328,24 +330,154 @@
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


# ═══════════════════════════════════════════════════════════════════════
# VM-19 (JODS-113) · Documentación del cliente mayorista
# ═══════════════════════════════════════════════════════════════════════
#
# DEC-10: los documentos son sensibles y viven en almacenamiento PRIVADO. La
# descarga pasa siempre por una vista con permisos; nunca hay una URL pública.
# DEC-11: no se borran automáticamente. Si una persona vuelve a solicitar, sus
# documentos anteriores siguen ahí como historial de lo que se revisó.
# DEC-16: los tipos documentales son configurables y NO hay requisitos
# obligatorios hasta que comercial los confirme. Por eso `TipoDocumento` no
# trae datos sembrados y nada en el sistema exige tener documentos.
# DEC-09: los carga el Administrador. El mayorista los consulta y descarga.


class TipoDocumento(models.Model):
    """Catálogo de tipos documentales (DEC-16), configurable en el panel.

    Nace vacío: qué documentos se piden es una decisión comercial pendiente.
    `obligatorio` existe para cuando se decida, pero **no está aplicado** en
    ninguna validación todavía; dejarlo puesto con valor `False` y sin uso es
    preferible a inventar una lista de requisitos.
    """

    nombre = models.CharField("nombre", max_length=80, unique=True)
    descripcion = models.TextField("descripción", blank=True)
    obligatorio = models.BooleanField(
        "obligatorio",
        default=False,
        help_text=(
            "Reservado para cuando comercial confirme qué documentos son "
            "imprescindibles. Hoy no se exige ninguno."
        ),
    )
    activo = models.BooleanField("activo", default=True)

    class Meta:
        ordering = ("nombre",)
        verbose_name = "tipo de documento"
        verbose_name_plural = "tipos de documento"

    def __str__(self):
        return self.nombre


def ruta_documento_mayorista(instancia, nombre_original):
    """`upload_to`: delega en el almacén privado (ver `mayoristas/storage.py`)."""
    from .storage import ruta_documento

    return ruta_documento(instancia, nombre_original)


class DocumentoSolicitud(models.Model):
    """Un archivo adjunto a una solicitud mayorista (VM-19, JODS-113).

    Decisión de diseño: el documento se enlaza a la SOLICITUD, no al usuario.
    Así, cuando alguien vuelve a solicitar tras un rechazo (DEC-08), los
    documentos de la solicitud anterior quedan asociados a esa solicitud y no
    se mezclan con los de la nueva. Es el historial que un revisor necesita.

    El archivo NO tiene URL pública (DEC-10): `archivo.url` no es utilizable y
    la descarga se hace por `mayoristas:descargar_documento`, que comprueba
    permisos. No hay `on_delete=CASCADE` desde el tipo documental: borrar un
    tipo no puede borrar documentos ya recibidos (DEC-11); se usa PROTECT.
    """

    solicitud = models.ForeignKey(
        SolicitudMayorista,
        on_delete=models.CASCADE,
        related_name="documentos",
        verbose_name="solicitud",
    )
    tipo = models.ForeignKey(
        TipoDocumento,
        on_delete=models.PROTECT,
        related_name="documentos",
        verbose_name="tipo de documento",
        null=True,
        blank=True,
        help_text="Opcional mientras no haya tipos configurados (DEC-16).",
    )
    archivo = models.FileField(
        "archivo",
        upload_to=ruta_documento_mayorista,
        storage=almacenamiento_privado,
        max_length=255,
    )
    nombre_original = models.CharField("nombre original", max_length=255, blank=True)
    descripcion = models.CharField("descripción", max_length=200, blank=True)
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documentos_subidos",
        verbose_name="subido por",
    )
    subido_en = models.DateTimeField("subido en", auto_now_add=True)

    class Meta:
        ordering = ("-subido_en",)
        verbose_name = "documento de solicitud"
        verbose_name_plural = "documentos de solicitud"

    def __str__(self):
        return f"{self.nombre_original or 'documento'} · {self.solicitud_id}"

    def save(self, *args, **kwargs):
        """Guarda el nombre original la primera vez, para poder mostrarlo."""
        if not self.nombre_original and self.archivo:
            self.nombre_original = self.archivo.name.rsplit("/", 1)[-1][:255]
        super().save(*args, **kwargs)

    @property
    def extension(self):
        """Extensión en minúsculas, para el icono de la lista."""
        nombre = self.nombre_original or (self.archivo.name if self.archivo else "")
        return nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""

    @property
    def tamano_legible(self):
        """Tamaño en KB o MB, para mostrarlo sin números largos."""
        try:
            bytes_archivo = self.archivo.size
        except (OSError, ValueError):
            return "—"
        if bytes_archivo >= 1024 * 1024:
            return f"{bytes_archivo / (1024 * 1024):.1f} MB"
        return f"{max(bytes_archivo // 1024, 1)} KB"