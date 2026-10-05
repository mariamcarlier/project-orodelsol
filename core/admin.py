from django.contrib import admin

from .models import Coleccion, Producto


@admin.register(Coleccion)
class ColeccionAdmin(admin.ModelAdmin):
	list_display = ("nombre", "temporada", "activa")
	list_filter = ("activa", "temporada")
	search_fields = ("nombre", "descripcion")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
	list_display = ("nombre", "coleccion", "precio", "destacado", "activo")
	list_filter = ("coleccion", "destacado", "activo")
	search_fields = ("nombre", "detalle", "descripcion")
