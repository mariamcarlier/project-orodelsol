from django.contrib import admin

from .models import Idioma, Impuesto, Moneda, ParametroGeneral


@admin.register(ParametroGeneral)
class ParametroGeneralAdmin(admin.ModelAdmin):
    list_display = (
        "nombre_tienda",
        "nit",
        "correo_contacto",
        "telefono_contacto",
        "actualizado_por",
        "fecha_actualizacion",
    )
    readonly_fields = ("actualizado_por", "fecha_actualizacion")

    def has_add_permission(self, request):
        return not ParametroGeneral.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Impuesto)
class ImpuestoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tasa", "vigente")
    list_filter = ("vigente",)
    search_fields = ("nombre",)
    actions = ("activar_impuestos", "desactivar_impuestos")

    @admin.action(description="Activar impuestos seleccionados")
    def activar_impuestos(self, request, queryset):
        queryset.update(vigente=True)

    @admin.action(description="Desactivar impuestos seleccionados")
    def desactivar_impuestos(self, request, queryset):
        queryset.update(vigente=False)


@admin.register(Moneda)
class MonedaAdmin(admin.ModelAdmin):
    list_display = (
        "codigo_iso",
        "nombre",
        "simbolo",
        "tasa_cambio",
        "es_principal",
        "activa",
    )
    list_filter = ("es_principal", "activa")
    search_fields = ("codigo_iso", "nombre")
    actions = ("activar_monedas", "desactivar_monedas")

    @admin.action(description="Activar monedas seleccionadas")
    def activar_monedas(self, request, queryset):
        queryset.update(activa=True)

    @admin.action(description="Desactivar monedas seleccionadas")
    def desactivar_monedas(self, request, queryset):
        queryset.update(activa=False)


@admin.register(Idioma)
class IdiomaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "es_principal", "activo")
    list_filter = ("es_principal", "activo")
    search_fields = ("codigo", "nombre")
    actions = ("activar_idiomas", "desactivar_idiomas")

    @admin.action(description="Activar idiomas seleccionados")
    def activar_idiomas(self, request, queryset):
        queryset.update(activo=True)

    @admin.action(description="Desactivar idiomas seleccionados")
    def desactivar_idiomas(self, request, queryset):
        queryset.update(activo=False)
