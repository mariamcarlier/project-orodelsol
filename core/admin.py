from django.contrib import admin

from .models import Coleccion, Producto


@admin.register(Coleccion)
class ColeccionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "temporada", "activa")
    list_filter = ("activa", "temporada")
    search_fields = ("nombre", "descripcion")
    actions = ("activar_colecciones", "desactivar_colecciones")

    @admin.action(description="Activar colecciones seleccionadas")
    def activar_colecciones(self, request, queryset):
        queryset.update(activa=True)

    @admin.action(description="Desactivar colecciones seleccionadas")
    def desactivar_colecciones(self, request, queryset):
        queryset.update(activa=False)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "coleccion", "precio", "destacado", "activo")
    list_filter = ("coleccion", "destacado", "activo")
    search_fields = ("nombre", "detalle", "descripcion")
    actions = ("activar_productos", "desactivar_productos")

    @admin.action(description="Activar productos seleccionados")
    def activar_productos(self, request, queryset):
        queryset.update(activo=True)

    @admin.action(description="Desactivar productos seleccionados")
    def desactivar_productos(self, request, queryset):
        queryset.update(activo=False)
