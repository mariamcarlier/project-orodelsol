from django.contrib import admin
from .models import Impuesto, Moneda, Idioma

@admin.register(Impuesto)
class ImpuestoAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'tasa', 'vigente')
    list_filter   = ('vigente',)
    search_fields = ('nombre',)

@admin.register(Moneda)
class MonedaAdmin(admin.ModelAdmin):
    list_display  = ('codigo_iso', 'nombre', 'simbolo', 'tasa_cambio', 'es_principal', 'activa')
    list_filter   = ('es_principal', 'activa')
    search_fields = ('codigo_iso', 'nombre')

@admin.register(Idioma)
class IdiomaAdmin(admin.ModelAdmin):
    list_display  = ('codigo', 'nombre', 'es_principal', 'activo')
    list_filter   = ('es_principal', 'activo')
    search_fields = ('codigo', 'nombre')
