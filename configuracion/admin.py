from django.contrib import admin
from .models import Impuesto

@admin.register(Impuesto)
class ImpuestoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tasa', 'vigente') # Columnas a mostrar en el panel
    list_filter = ('vigente',)                   # Filtro lateral
    search_fields = ('nombre',)                  # Barra de búsqueda