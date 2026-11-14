from django.contrib import admin, messages
from .models import Coleccion, Material, Piedra, Producto, Talla, VarianteProducto


@admin.register(Coleccion)
class ColeccionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "temporada", "activa")
    list_filter = ("activa", "temporada")
    search_fields = ("nombre", "descripcion")
    # La portada por archivo (`imagen`) se sube desde el panel y desde el
    # formulario de colecciones, que la validan y la optimizan (`ColeccionForm`,
    # Paso 04). Este admin genera su propio formulario, sin esa validación: sin
    # esta línea mostraría un campo de subida abierto que acepta cualquier
    # imagen, sin límite de peso. (`imagen_detalle` no hace falta excluirlo: no
    # es editable y ningún formulario lo ofrece.)
    exclude = ("imagen",)
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


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "coleccion", "precio", "personalizable", "destacado", "activo", "es_borrador")
    list_filter = ("coleccion", "personalizable", "destacado", "activo", "es_borrador")
    search_fields = ("codigo", "nombre", "detalle", "descripcion")
    filter_horizontal = ("tallas", "materiales", "piedras")
    inlines = (VarianteProductoInline,)
    actions = ("activar_productos", "desactivar_productos")

    @admin.action(description="Activar productos seleccionados")
    def activar_productos(self, request, queryset):
        omitidos = queryset.incompletos().count()
        # Publicar un borrador completo también lo saca de borrador.
        queryset.completos().update(activo=True, es_borrador=False)
        if omitidos:
            self.message_user(
                request,
                f"{omitidos} producto(s) no se activaron: les falta nombre, "
                "código, imagen o un precio mayor a cero.",
                level=messages.WARNING,
            )

    @admin.action(description="Desactivar productos seleccionados")
    def desactivar_productos(self, request, queryset):
        queryset.update(activo=False)


@admin.register(Talla)
class TallaAdmin(admin.ModelAdmin):
    list_display = ("talla_us", "talla_nacional", "diametro_interno_mm", "diametro_verificado")
    list_filter = ("diametro_verificado",)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)


@admin.register(Piedra)
class PiedraAdmin(admin.ModelAdmin):
    list_display = ("ref", "nombre", "imagen", "orden")
    list_editable = ("nombre", "orden")
    search_fields = ("ref", "nombre")


@admin.register(VarianteProducto)
class VarianteProductoAdmin(admin.ModelAdmin):
    list_display = ("sku", "producto", "talla", "material", "stock", "precio_adicional", "activa")
    list_filter = ("activa", "material", "talla")
    search_fields = ("sku", "producto__nombre", "producto__codigo")