from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import EditarPerfilForm, RegistroClienteForm, RegistroUsuarioForm
from .secciones import pagina_para, tarjetas_para


def es_administrador(user):
    # La regla vive en el modelo (Usuario.es_administrador); aquí solo se comprueba la sesión.
    return user.is_authenticated and user.es_administrador


def imagen_banner_cuenta(usuario):
    """Devuelve la URL de la imagen de la cabecera de «Mi cuenta», o None.

    PUNTO ÚNICO DE DECISIÓN. Hoy no hay una imagen administrable, así que
    devuelve None y la cabecera se ve con su color por defecto (el degradado
    rosa y oro rosa de .account-hero en static/css/perfil.css).

    Para que el administrador pueda cambiarla desde el panel (cada paso, en su
    propio commit):
      1. Agregar un campo de imagen en la configuración, por ejemplo
         imagen_banner_cuenta = models.ImageField(upload_to="banners/", blank=True)
         en configuracion.ParametroGeneral, con su migración y su formulario en
         el panel (junto a los demás parámetros generales).
      2. Devolver aquí su URL cuando tenga una imagen cargada:
             imagen = ParametroGeneral.get_solo().imagen_banner_cuenta
             return imagen.url if imagen else None
         Si se quiere una imagen distinta por tipo de cuenta, se decide aquí con
         usuario.rol_efectivo.
      3. No hay nada más que cambiar: la plantilla muestra la imagen cuando recibe
         una URL y vuelve sola al color por defecto cuando recibe None.

    Medidas recomendadas: 2400 × 800 px (3:1), WebP de menos de 200 KB, con el
    motivo en el 60 % derecho. Debe tener derechos de uso comercial.
    """
    return None


def migas_cuenta(ultima=None):
    """Migas de pan de la cuenta: (texto, url). La página actual va sin enlace (url None).

    Sin «ultima» se está en «Mi cuenta» y esa es la página actual; con «ultima»
    «Mi cuenta» pasa a ser un enlace de regreso.
    """
    migas = [("Inicio", reverse("core:inicio"))]
    if ultima:
        migas += [("Mi cuenta", reverse("usuarios:perfil")), ultima]
    else:
        migas.append(("Mi cuenta", None))
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
            # None = color por defecto; con URL se muestra la imagen (ver imagen_banner_cuenta).
            "banner_imagen_url": imagen_banner_cuenta(usuario),
            # Tarjetas según el tipo de cuenta (ver usuarios/secciones.py).
            "tarjetas": tarjetas_para(usuario),
            "breadcrumbs": migas_cuenta(),
        },
    )


@login_required
def seccion_cuenta(request, clave):
    pagina = pagina_para(request.user, clave)
    if pagina is None:
        raise Http404("La sección solicitada no está disponible.")

    return render(
        request,
        "usuarios/seccion_cuenta.html",
        {
            "titulo_seccion": pagina["titulo"],
            "breadcrumbs": migas_cuenta((pagina["titulo"], None)),
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