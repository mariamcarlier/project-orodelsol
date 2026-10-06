# 1. Primero realiza las importaciones
from django.db.models import Count, Q
from django.shortcuts import render

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