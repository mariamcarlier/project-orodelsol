# 1. Primero realiza las importaciones
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import render

from configuracion.decorators import admin_required

from .models import Coleccion, Producto

Usuario = get_user_model()


def inicio(request):
    colecciones = Coleccion.objects.filter(activa=True).annotate(
        producto_count=Count("productos", filter=Q(productos__activo=True))
    )
    productos = Producto.objects.filter(activo=True).select_related("coleccion")[:4]
    return render(
        request,
        "core/index.html",
        {"colecciones": colecciones, "productos": productos},
    )


@admin_required
def admin_dashboard(request):
    """Vista del panel administrativo con métricas generales y productos recientes."""
    active_product_count = Producto.objects.filter(activo=True).count()
    active_collection_count = Coleccion.objects.filter(activa=True).count()
    active_client_count = Usuario.objects.filter(is_active=True, rol="CLIENTE").count()
    recent_products = Producto.objects.filter(activo=True).select_related("coleccion")[:5]

    context = {
        "active_product_count": active_product_count,
        "active_collection_count": active_collection_count,
        "active_client_count": active_client_count,
        "recent_products": recent_products,
    }
    return render(request, "admin_custom/index.html", context)