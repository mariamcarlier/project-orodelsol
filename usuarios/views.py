

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render

from .forms import EditarPerfilForm, RegistroUsuarioForm


def es_administrador(user):
    return user.is_authenticated and (user.is_superuser or user.rol == "ADMIN")


@login_required
@user_passes_test(es_administrador)
def registrar_usuario(request):
    if request.method == "POST":
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario registrado correctamente.")
            return redirect("usuarios:registrar_usuario")
        messages.error(
            request,
            "No se pudo registrar el usuario. Revisa los campos marcados.",
        )
    else:
        form = RegistroUsuarioForm()

    return render(request, "usuarios/registrar.html", {"form": form})


@login_required
def perfil(request):
    return render(request, "usuarios/perfil.html", {"perfil": request.user})


@login_required
def editar_perfil(request):
    if request.method == "POST":
        form = EditarPerfilForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Tu información se actualizó correctamente.")
            return redirect("usuarios:editar_perfil")
        messages.error(
            request,
            "No se pudo guardar: revisa los campos marcados en rojo.",
        )
    else:
        form = EditarPerfilForm(instance=request.user)

    return render(request, "usuarios/editar_perfil.html", {"form": form})
