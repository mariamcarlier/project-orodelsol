"""Vistas del canal B2B.

VM-01 (JODS-95): registro de la solicitud de acceso mayorista y consulta de
su estado.

Decisión DEC-05: el estado de la solicitud se consulta en una página propia de
`mayoristas` (`/mayoristas/solicitud/`), no en la tarjeta «Estado de mi
solicitud» de «Mi cuenta». Así no se toca `usuarios` ni se rompen sus
invariantes de pruebas. La tarjeta de «Mi cuenta» queda como deuda de UX
documentada en Jira.

Ninguna vista cambia el estado de una solicitud: eso llega con VM-02.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from . import selectors
from .forms import SolicitudMayoristaForm
from .servicios import registrar_solicitud


def _migas(*ultimas):
    """Migas de pan: Inicio › [página actual]."""
    migas = [("Inicio", reverse("core:inicio"))]
    for texto in ultimas:
        migas.append((texto, None))
    return migas


@login_required
@require_http_methods(["GET", "POST"])
def solicitar_acceso(request):
    """Formulario de registro del mayorista.

    Quien ya tiene una solicitud activa no vuelve a verlo: se le manda a la
    página de estado, que le explica en qué punto está. Un administrador
    tampoco registra solicitudes.
    """
    usuario = request.user

    if usuario.es_administrador:
        messages.info(
            request,
            "Tu cuenta es de administración: no necesita solicitud de acceso mayorista.",
        )
        return redirect("usuarios:perfil")

    decision = selectors.puede_solicitar(usuario)
    if not decision["puede"]:
        messages.info(request, decision["motivo"])
        return redirect("mayoristas:mi_solicitud")

    if request.method == "POST":
        form = SolicitudMayoristaForm(request.POST)
        if form.is_valid():
            try:
                registrar_solicitud(usuario, form.cleaned_data)
            except ValidationError as exc:
                # El servicio devuelve mensajes ya redactados para la pantalla.
                form.add_error(None, exc.messages if hasattr(exc, "messages") else exc)
            else:
                messages.success(
                    request,
                    "Recibimos tu solicitud. Te avisaremos por correo cuando la revisemos.",
                )
                return redirect("mayoristas:mi_solicitud")
    else:
        form = SolicitudMayoristaForm()

    return render(
        request,
        "mayoristas/solicitar.html",
        {
            "form": form,
            "breadcrumbs": _migas("Solicitud de acceso"),
        },
    )


@login_required
def mi_solicitud(request):
    """Estado de la solicitud del usuario autenticado (nunca la de otro).

    No recibe identificador por URL: la búsqueda se hace siempre con
    `request.user`. Así no existe forma de pedir la solicitud de otra persona
    cambiando un número (acceso horizontal).
    """
    solicitud = selectors.ultima_solicitud_de(request.user)
    return render(
        request,
        "mayoristas/mi_solicitud.html",
        {
            "solicitud": solicitud,
            "puede_volver_a_solicitar": (
                solicitud is not None and solicitud.estado == "RECHAZADA"
            ),
            "breadcrumbs": _migas("Estado de mi solicitud"),
        },
    )
