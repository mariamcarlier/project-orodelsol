from django.contrib import admin, messages

from .models import Coleccion, Material, Producto, Talla, VarianteProducto
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


class VarianteProductoInline(admin.TabularInline):
    model = VarianteProducto
    extra = 0
    # Primero guarda el producto con sus tallas y materiales permitidos y
    # después agrega variantes: la variante solo acepta lo permitido.


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "coleccion", "precio", "destacado", "activo", "es_borrador")
    list_filter = ("coleccion", "destacado", "activo", "es_borrador")
    search_fields = ("codigo", "nombre", "detalle", "descripcion")
    filter_horizontal = ("tallas", "materiales")
    inlines = (VarianteProductoInline,)
@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "coleccion", "precio", "destacado", "activo")
    list_filter = ("coleccion", "destacado", "activo")
    search_fields = ("nombre", "detalle", "descripcion")
    actions = ("activar_productos", "desactivar_productos")

    @admin.action(description="Activar productos seleccionados")
    def activar_productos(self, request, queryset):
        # update() no pasa por clean(): solo se activan los productos completos.
        omitidos = queryset.incompletos().count()
        queryset.completos().update(activo=True)
        if omitidos:
            self.message_user(
                request,
                f"{omitidos} producto(s) no se activaron: les falta nombre, "
                "código, imagen o un precio mayor a cero.",
                level=messages.WARNING,
            )
        queryset.update(activo=True)

    @admin.action(description="Desactivar productos seleccionados")
    def desactivar_productos(self, request, queryset):
        queryset.update(activo=False)


@admin.register(Talla)
class TallaAdmin(admin.ModelAdmin):
    list_display = ("talla_us", "diametro_interno_mm", "diametro_verificado")
    list_filter = ("diametro_verificado",)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)


@admin.register(VarianteProducto)
class VarianteProductoAdmin(admin.ModelAdmin):
    list_display = ("sku", "producto", "talla", "material", "stock", "precio_adicional", "activa")
    list_filter = ("activa", "material", "talla")
    search_fields = ("sku", "producto__nombre", "producto__codigo")
