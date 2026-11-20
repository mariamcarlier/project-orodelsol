"""Admin de Django para el canal B2B.

El admin es **complementario**, no la bandeja (DEC-04): aquí se consulta y se
edita el registro para tareas de soporte, pero la decisión de aprobar o
rechazar se toma en `/mayoristas/bandeja/`, que es donde viven el permiso del
módulo, las reglas de transición y la notificación al cliente.

En el admin se quitan `estado`, `motivo_rechazo`, `revisado_por` y
`revisado_en` de la edición: son los campos que cambian por el servicio, y
dejarlos editables aquí permitiría saltarse las reglas (aprobar sin avisar,
rechazar sin motivo, re-revisar una decisión tomada).
"""

from django.contrib import admin

from .models import SolicitudMayorista


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
