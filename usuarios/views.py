from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import EditarPerfilForm, RegistroClienteForm, RegistroUsuarioForm


def es_administrador(user):
    return user.is_authenticated and (user.is_superuser or user.rol == "ADMIN")


# Secciones de la cuenta y roles que pueden verlas.
# Las claves son los <slug> de la URL. Cuando existan modelos
# (Pedido, Cotizacion, Direccion...), cada clave podrá tener su
# propio template con datos reales en lugar del estado vacío.
SECCIONES_CUENTA = {
    "tallas":          {"titulo": "Mis Tallas",             "roles": {"CLIENTE", "MAYORISTA"}},
    "direcciones":     {"titulo": "Libreta de Direcciones", "roles": {"CLIENTE", "MAYORISTA"}},
    "lista-de-deseos": {"titulo": "Mi Lista de Deseos",     "roles": {"CLIENTE", "MAYORISTA"}},
    "pedido-reciente": {"titulo": "Mi Pedido Reciente",     "roles": {"CLIENTE", "MAYORISTA"}},
    "empresa":         {"titulo": "Datos de mi Empresa",    "roles": {"MAYORISTA"}},
    "solicitud":       {"titulo": "Estado de mi Solicitud", "roles": {"MAYORISTA"}},
    "cotizaciones":    {"titulo": "Mis Cotizaciones",       "roles": {"MAYORISTA"}},
}


def rol_efectivo(usuario):
    """Rol mostrado en pantalla.

    Un superusuario creado con createsuperuser conserva rol='CLIENTE'
    (default del campo), pero para presentación siempre es Administrador.
    Mismo criterio que es_administrador().
    """
    if usuario.is_superuser or usuario.rol == "ADMIN":
        return "Administrador"
    return usuario.get_rol_display()


def migas_cuenta(ultima=None):
    migas = [
        ("Inicio", reverse("core:inicio")),
        ("Mi cuenta", reverse("usuarios:perfil")),
    ]
    if ultima:
        migas.append(ultima)
    return migas


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


@login_required
def perfil(request):
    usuario = request.user
    return render(
        request,
        "usuarios/perfil.html",
        {
            "perfil": usuario,
            # Fallback seguro: nunca muestra "None" ni cadena vacía.
            "nombre_bienvenida": (usuario.first_name or "").strip() or usuario.username,
            "rol_efectivo": rol_efectivo(usuario),
            "es_admin": usuario.is_superuser or usuario.rol == "ADMIN",
            "breadcrumbs": migas_cuenta(),
        },
    )


@login_required
def seccion_cuenta(request, clave):
    seccion = SECCIONES_CUENTA.get(clave)
    if seccion is None or request.user.rol not in seccion["roles"]:
        raise Http404("La sección solicitada no está disponible.")

    return render(
        request,
        "usuarios/seccion_cuenta.html",
        {
            "titulo_seccion": seccion["titulo"],
            "breadcrumbs": migas_cuenta((seccion["titulo"], None)),
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