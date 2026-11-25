"""Admin de Django para el canal B2B.

El admin es **complementario**, no la bandeja (DEC-04): aquí se consulta y se edita el registro para tareas de soporte, pero la decisión de aprobar o rechazar se toma en `/mayoristas/bandeja/`, que es donde viven el permiso del módulo, las reglas de transición y la notificación al cliente.

En el admin se quitan `estado`, `motivo_rechazo`, `revisado_por` y `revisado_en` de la edición: son los campos que cambian por el servicio, y dejarlos editables aquí permitiría saltarse las reglas (aprobar sin avisar, rechazar sin motivo, re-revisar una decisión tomada).
"""
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

# Register your models here.
from .models import (DiaNoHabil,
    DocumentoSolicitud,
    SolicitudMayorista,
    TipoDocumento,
    TramoPrecioReferencia,
)


@admin.register(SolicitudMayorista)
class SolicitudMayoristaAdmin(admin.ModelAdmin):
    list_display = (
        "nombre_comercial",
        "nit",
        "ciudad",
        "estado",
        "creado_en",
        "revisado_en",
    )
    list_filter = ("estado", "tipo_persona", "creado_en")
    search_fields = ("nombre_comercial", "nit", "ciudad", "correo", "usuario__email")
    list_select_related = ("usuario", "revisado_por")
    date_hierarchy = "creado_en"
    ordering = ("-creado_en",)
    readonly_fields = (
        "estado",
        "motivo_rechazo",
        "revisado_por",
        "revisado_en",
        "creado_en",
    )
    fieldsets = (
        (
            "Negocio",
            {
                "fields": (
                    "usuario",
                    "tipo_persona",
                    "nit",
                    "nombre_comercial",
                    "representante_legal",
                )
            },
        ),
        ("Contacto", {"fields": ("ciudad", "telefono", "correo")}),
        ("Contexto comercial", {"fields": ("canal_venta", "referido")}),
        (
            "Revisión",
            {
                "fields": (
                    "estado",
                    "motivo_rechazo",
                    "revisado_por",
                    "revisado_en",
                    "creado_en",
                ),
                "description": (
                    "La decisión se toma en la bandeja de solicitudes, no aquí: "
                    "así se aplican las reglas y se notifica al cliente."
                ),
            },
        ),
    )

    def has_add_permission(self, request):
        """No se crean solicitudes desde el admin: las crea el cliente."""
        return False


@admin.register(TramoPrecioReferencia)
class TramoPrecioReferenciaAdmin(admin.ModelAdmin):
    """Configuración de los tramos B2B (DEC-02).

    El porcentaje se deja VACÍO a propósito: es una decisión comercial, no una
    decisión técnica. Mientras esté vacío el tramo no se aplica y el catálogo
    avisa «Tramos pendientes de configuración» (DEC-18).
    """

    list_display = (
        "nombre",
        "rango_display",
        "porcentaje",
        "configurado",
        "activo",
    )
    list_filter = ("activo",)
    ordering = ("cantidad_minima",)
    search_fields = ("nombre",)
    list_editable = ("activo",)

    def get_readonly_fields(self, request, obj=None):
        # Una vez usado en cotizaciones, el rango no se reescribe a la ligera.
        return ()


@admin.register(DiaNoHabil)
class DiaNoHabilAdmin(admin.ModelAdmin):
    """Calendario de festivos para el SLA de 24–48 h hábiles (RN-VM-06)."""

    list_display = ("fecha", "nombre")
    ordering = ("fecha",)
    search_fields = ("nombre",)
    date_hierarchy = "fecha"
    
# ═══════════════════════════════════════════════════════════════════════
# VM-19 (JODS-113) · Tipos de documento y documentos
# ═══════════════════════════════════════════════════════════════════════


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    """Tipos documentales (DEC-16). El administrador los crea cuando los
    defina comercial; no se siembra ninguno."""

    list_display = ("nombre", "obligatorio", "activo", "documentos_recibidos")
    list_filter = ("obligatorio", "activo")
    list_editable = ("obligatorio", "activo")
    search_fields = ("nombre", "descripcion")

    @admin.display(description="Documentos recibidos")
    def documentos_recibidos(self, obj):
        return obj.documentos.count()


@admin.register(DocumentoSolicitud)
class DocumentoSolicitudAdmin(admin.ModelAdmin):
    """Documentos adjuntos.

    El archivo NO es un enlace a un medio público: `descargar` apunta a la
    vista autorizada, para que ni siquiera desde el admin se genere una URL
    servible del almacén privado (DEC-10).
    """

    list_display = ("nombre_original", "solicitud", "tipo", "subido_en", "descargar")
    list_filter = ("tipo", "subido_en")
    search_fields = ("nombre_original", "descripcion", "solicitud__nombre_comercial")
    readonly_fields = ("nombre_original", "subido_por", "subido_en", "descargar")
    autocomplete_fields = ("solicitud",)

    @admin.display(description="Archivo")
    def descargar(self, obj):
        if not obj.pk:
            return "—"
        url = reverse("mayoristas:descargar_documento", args=[obj.pk])
        return format_html('<a href="{}">Descargar</a>', url)