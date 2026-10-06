from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from django.shortcuts import render

from usuarios.views import es_administrador

from .models import Coleccion, Producto


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


@login_required
@user_passes_test(es_administrador)
def admin_dashboard(request):
    return render(
        request,
        "admin_custom/index.html",
        {
            "active_product_count": Producto.objects.filter(activo=True).count(),
            "active_collection_count": Coleccion.objects.filter(activa=True).count(),
            "active_client_count": get_user_model()
            .objects.filter(rol="CLIENTE", is_active=True)
            .count(),
            "recent_products": Producto.objects.select_related("coleccion").order_by(
                "-pk"
            )[:5],
        },
    )