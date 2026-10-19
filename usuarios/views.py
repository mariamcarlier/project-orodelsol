

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render

from .forms import EditarPerfilForm, RegistroClienteForm, RegistroUsuarioForm


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


def crear_cuenta(request):
    if request.method == "POST":
        form = RegistroClienteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Tu cuenta se creó correctamente. Ya puedes iniciar sesión.",
            )
            return redirect("login")
    else:
        form = RegistroClienteForm()

    return render(
        request,
        "usuarios/registrar.html",
        {"form": form, "registro_publico": True},
    )


def imagen_banner_cuenta(usuario):
    """Devuelve la URL de la imagen de fondo de la cabecera de la cuenta, o None.

    PUNTO ÚNICO DE DECISIÓN. Hoy no existe una imagen administrable, así que
    devuelve None y la cabecera se muestra con el degradado de marca
    (clase .account-hero en static/css/components.css).

    Para poder administrarla más adelante (cada paso, en su propio commit):
      1. Agregar un campo de imagen en la configuración (por ejemplo en
         ParametroGeneral) con su migración y su formulario en el panel.
      2. Devolver aquí la URL de ese campo cuando tenga una imagen cargada.
         Si se quiere una imagen distinta por tipo de cuenta, se decide aquí
         con usuario.tipo_cuenta.
      3. No hay nada más que cambiar: la plantilla ya muestra la imagen
         cuando recibe una URL y vuelve al degradado cuando recibe None.
    """
    return None


@login_required
def perfil(request):
    return render(
        request,
        "usuarios/perfil.html",
        {
            "perfil": request.user,
            "banner_imagen_url": imagen_banner_cuenta(request.user),
        },
    )


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
