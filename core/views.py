from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .dashboard import ColeccionForm, ProductoForm, admin_dashboard, admin_section
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
def producto_listar(request):
    productos = Producto.objects.select_related("coleccion").all()
    return render(request, "core/productos/listar.html", {"productos": productos})


@login_required
def producto_guardar(request, pk=None):
    instancia = get_object_or_404(Producto, pk=pk) if pk else None
    form = ProductoForm(request.POST or None, request.FILES or None, instance=instancia)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Producto guardado correctamente.")
        return redirect("core:producto_listar")

    titulo = "Editar producto" if instancia else "Nuevo producto"
    return render(
        request,
        "core/productos/form.html",
        {"form": form, "titulo": titulo},
    )


@login_required
def producto_eliminar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == "POST":
        producto.delete()
        messages.success(request, "Producto eliminado correctamente.")
    return redirect("core:producto_listar")


class ColeccionListView(LoginRequiredMixin, ListView):
    model = Coleccion
    template_name = "core/colecciones/listar.html"
    context_object_name = "colecciones"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Colecciones"
        return context


class ColeccionCreateView(LoginRequiredMixin, CreateView):
    model = Coleccion
    form_class = ColeccionForm
    template_name = "core/colecciones/form.html"
    success_url = reverse_lazy("core:coleccion_listar")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Nueva colección"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Colección creada correctamente.")
        return super().form_valid(form)


class ColeccionUpdateView(LoginRequiredMixin, UpdateView):
    model = Coleccion
    form_class = ColeccionForm
    template_name = "core/colecciones/form.html"
    success_url = reverse_lazy("core:coleccion_listar")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = f"Editar colección: {self.object.nombre}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Colección actualizada correctamente.")
        return super().form_valid(form)


class ColeccionDeleteView(LoginRequiredMixin, DeleteView):
    model = Coleccion
    template_name = "core/colecciones/confirmar_eliminar.html"
    success_url = reverse_lazy("core:coleccion_listar")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = f"Eliminar colección: {self.object.nombre}"
        return context

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "No se puede eliminar esta colección porque tiene productos asociados.",
            )
            return redirect(self.success_url)

        messages.success(self.request, "Colección eliminada correctamente.")
        return response
