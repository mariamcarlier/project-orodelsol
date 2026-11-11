from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from . import servicio_galeria
from .dashboard import ColeccionForm, ProductoForm, admin_dashboard, admin_section
from .models import Coleccion, Producto
from .vistas_galeria import contexto_galeria


# ---------------------------------------------------------------------------
# Mixin de autorización para las CBV administrativas
# ---------------------------------------------------------------------------
# Exige is_staff=True (como @staff_member_required) más el permiso Django
# específico de cada vista. Es la misma política que usa el dashboard.
# ---------------------------------------------------------------------------

class StaffPermissionMixin(PermissionRequiredMixin):
    """Exige is_staff y el permiso Django indicado en cada vista."""

    raise_exception = True

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_staff:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Catálogo público (sin restricción de acceso)
# ---------------------------------------------------------------------------

def inicio(request):
    colecciones = Coleccion.objects.filter(activa=True).annotate(
        producto_count=Count(
            "productos",
            filter=Q(productos__activo=True, productos__es_borrador=False),
        )
    )
    productos = Producto.objects.publicos().select_related("coleccion")[:4]
    return render(
        request,
        "core/index.html",
        {"colecciones": colecciones, "productos": productos},
    )


# ---------------------------------------------------------------------------
# Productos — vistas de función protegidas con is_staff + has_perm
# ---------------------------------------------------------------------------

@staff_member_required
def producto_listar(request):
    if not request.user.has_perm("core.view_producto"):
        raise PermissionDenied
    productos = Producto.objects.select_related("coleccion").all()
    return render(request, "core/productos/listar.html", {"productos": productos})


# El orden importa: staff_member_required (autenticación/autorización)
# envuelve a require_http_methods, de modo que un usuario sin acceso
# recibe la respuesta de autenticación/autorización que le corresponde y
# solo se evalúa el método HTTP cuando la identidad ya fue aceptada.
@staff_member_required
@require_http_methods(["GET", "POST"])
def producto_guardar(request, pk=None):
    # `pk is not None` (y no `if pk:`) para que pk=0 —inválido, nunca
    # existe en la BD— caiga en get_object_or_404 y devuelva 404 en vez
    # de entrar en la rama de creación.
    if pk is not None:
        if not request.user.has_perm("core.change_producto"):
            raise PermissionDenied
        instancia = get_object_or_404(Producto, pk=pk)
    else:
        if not request.user.has_perm("core.add_producto"):
            raise PermissionDenied
        instancia = None

    form = ProductoForm(request.POST or None, request.FILES or None, instance=instancia)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Producto guardado correctamente.")
        return redirect("core:producto_listar")

    titulo = "Editar producto" if instancia else "Nuevo producto"
    contexto = {"form": form, "titulo": titulo}
    if instancia:
        # La galería necesita un producto ya guardado: solo aparece al editar.
        contexto["galeria"] = contexto_galeria(
            instancia, servicio_galeria.listar(instancia)
        )
    return render(request, "core/productos/form.html", contexto)


@require_POST
@staff_member_required
def producto_eliminar(request, pk):
    if not request.user.has_perm("core.delete_producto"):
        raise PermissionDenied
    producto = get_object_or_404(Producto, pk=pk)
    producto.delete()
    messages.success(request, "Producto eliminado correctamente.")
    return redirect("core:producto_listar")


# ---------------------------------------------------------------------------
# Colecciones — CBV protegidas con StaffPermissionMixin
# ---------------------------------------------------------------------------

class ColeccionListView(StaffPermissionMixin, ListView):
    http_method_names = ["get", "head", "options"]
    model = Coleccion
    template_name = "core/colecciones/listar.html"
    context_object_name = "colecciones"
    permission_required = "core.view_coleccion"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Colecciones"
        return context


class ColeccionCreateView(StaffPermissionMixin, CreateView):
    http_method_names = ["get", "post", "head", "options"]
    model = Coleccion
    form_class = ColeccionForm
    template_name = "core/colecciones/form.html"
    success_url = reverse_lazy("core:coleccion_listar")
    permission_required = "core.add_coleccion"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Nueva colección"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Colección creada correctamente.")
        return super().form_valid(form)


class ColeccionUpdateView(StaffPermissionMixin, UpdateView):
    http_method_names = ["get", "post", "head", "options"]
    model = Coleccion
    form_class = ColeccionForm
    template_name = "core/colecciones/form.html"
    success_url = reverse_lazy("core:coleccion_listar")
    permission_required = "core.change_coleccion"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = f"Editar colección: {self.object.nombre}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Colección actualizada correctamente.")
        return super().form_valid(form)


class ColeccionDeleteView(StaffPermissionMixin, DeleteView):
    # GET muestra la confirmación, POST confirma; DELETE queda excluido
    # para que ninguna petición pueda eliminar directamente.
    http_method_names = ["get", "post", "head", "options"]
    model = Coleccion
    template_name = "core/colecciones/confirmar_eliminar.html"
    success_url = reverse_lazy("core:coleccion_listar")
    permission_required = "core.delete_coleccion"

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