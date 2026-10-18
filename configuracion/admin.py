from django.contrib import admin
from .models import CostoEnvio, Idioma, Impuesto, MetodoPago, Moneda, ParametroGeneral


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


@admin.register(CostoEnvio)
class CostoEnvioAdmin(admin.ModelAdmin):
    list_display = (
        "ciudad",
        "departamento",
        "precio",
        "tiempo_entrega",
        "activo",
    )
    list_filter = ("departamento", "activo")
    search_fields = ("ciudad", "departamento")
    ordering = ("departamento", "ciudad")
    actions = ("activar_tarifas", "desactivar_tarifas")

    @admin.action(description="Activar tarifas seleccionadas")
    def activar_tarifas(self, request, queryset):
        queryset.update(activo=True)

    @admin.action(description="Desactivar tarifas seleccionadas")
    def desactivar_tarifas(self, request, queryset):
        queryset.update(activo=False)


@admin.register(MetodoPago)
class MetodoPagoAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "tipo",
        "banco",
        "numero_cuenta",
        "titular",
        "activo",
        "orden",
    )
    list_filter = ("tipo", "activo")
    search_fields = ("nombre", "banco", "titular", "numero_cuenta")
    ordering = ("orden", "nombre")
    actions = ("activar_metodos", "desactivar_metodos")

    @admin.action(description="Activar métodos de pago seleccionados")
    def activar_metodos(self, request, queryset):
        queryset.update(activo=True)

    @admin.action(description="Desactivar métodos de pago seleccionados")
    def desactivar_metodos(self, request, queryset):
        queryset.update(activo=False)

