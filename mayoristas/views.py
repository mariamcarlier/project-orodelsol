"""Vistas del canal B2B.

VM-01 (JODS-95): registro de la solicitud de acceso mayorista y consulta de su estado.Decisión DEC-05: el estado de la solicitud se consulta en una página propia de `mayoristas` (`/mayoristas/solicitud/`), no en la tarjeta «Estado de mi solicitud» de «Mi cuenta». Así no se toca `usuarios` ni se rompen sus invariantes de pruebas. La tarjeta de «Mi cuenta» queda como deuda de UX documentada en Jira.

VM-02 (JODS-96): bandeja de verificación, ficha de revisión y decisión (aprobar / rechazar).

DEC-04: la bandeja vive en `mayoristas`, no en `core/dashboard.py`. El panel del proyecto es una configuración declarativa por modelo (crear, editar, borrar) que no admite acciones de negocio como «aprobar»; llevarla allí habría obligado a tocar `core` y a mezclar dos formas de trabajo.

DEC-06: los cambios de estado son POST. Un GET sobre las rutas de decisión devuelve 405 aunque quien lo pida tenga permiso, para que ni un enlace, ni una precarga del navegador, ni un rastreador aprueben nada por accidente.

DEC-07: los permisos son propios del módulo (`ver_bandeja_solicitudesmayoristas` y `gestionar_solicitudesmayoristas`). No se exige `is_staff` ni se conceden permisos administrativos generales: una cuenta de revisión puede ser una cuenta normal que solo tenga esos dos. La decisión nunca toca `is_staff` ni `is_superuser`.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.generic import DetailView, TemplateView, View

from . import selectors, servicios
from .forms import RechazoSolicitudForm, SolicitudMayoristaForm
from .models import SolicitudMayorista
from .servicios import (
    aprobar_solicitud,
    rechazar_solicitud,
    registrar_solicitud,
)


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
    No recibe identificador por URL: la búsqueda se hace siempre con `request.user`. Así no existe forma de pedir la solicitud de otra persona cambiando un número (acceso horizontal).
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


# ═══════════════════════════════════════════════════════════════════════
# VM-02 (JODS-96) · Bandeja de verificación y decisión
# ═══════════════════════════════════════════════════════════════════════

PERMISO_VER = "mayoristas.ver_bandeja_solicitudesmayoristas"
PERMISO_GESTIONAR = "mayoristas.gestionar_solicitudesmayoristas"


class BandejaPermissionMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Exige sesión iniciada y el permiso del módulo, en ese orden.

    El orden importa: un visitante anónimo debe acabar en el login (302) y no en un 403, porque un 403 le confirmaría que la página existe. Quien ya
    entró pero no tiene permiso recibe 403, nunca una redirección silenciosa que parezca un error de la aplicación.

    La distinción se deja EN MANOS DE DJANGO (`AccessMixin.handle_no_permission`)
    en lugar de fijar `raise_exception = True`: con esa bandera activa,`LoginRequiredMixin` también lanzaba 403 al anónimo. Django ya hace lo que
    queremos: si no hay sesión, redirige al login con `?next=`; si hay sesión pero falta el permiso, lanza `PermissionDenied` (403).

    El permiso se exige tanto para VER como para DECIDIR; decidir además requiere `gestionar`, que se comprueba en cada vista de acción.
    """

    permission_required = PERMISO_VER


def _migas_bandeja(*ultimas):
    """Migas: Inicio › Solicitudes de mayoristas › [página actual]."""
    migas = [
        ("Inicio", reverse("core:inicio")),
        ("Solicitudes de mayoristas", reverse("mayoristas:bandeja")),
    ]
    for texto in ultimas:
        migas.append((texto, None))
    return migas


class BandejaSolicitudesView(BandejaPermissionMixin, TemplateView):
    """Listado de solicitudes con filtro por estado y búsqueda libre.

    Las tres cifras se muestran siempre, incluso filtrando: quien revisa
    necesita saber cuántas quedan pendientes sin tener que volver a «todas».
    """

    template_name = "mayoristas/bandeja.html"
    permission_required = PERMISO_VER

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        estado_filtro = (self.request.GET.get("estado") or "").upper()
        busqueda = self.request.GET.get("q") or ""

        contexto.update(
            {
                "solicitudes": selectors.bandeja_solicitudes(estado_filtro, busqueda),
                "resumen": selectors.resumen_bandeja(),
                "estado_filtro": (
                    estado_filtro if estado_filtro in selectors.ESTADOS_FILTRO else ""
                ),
                "busqueda": busqueda,
                "estados": SolicitudMayorista.Estado.choices,
                "puede_gestionar": self.request.user.has_perm(PERMISO_GESTIONAR),
                "breadcrumbs": _migas_bandeja(),
            }
        )
        return contexto
    
    
class DetalleSolicitudView(BandejaPermissionMixin, DetailView):
    """Ficha completa de una solicitud y sus acciones de decisión.

    Solo las PENDIENTES muestran botones: ofrecer una acción que el servicio
    va a rechazar por DEC-08 sería un botón que siempre falla.
    """

    template_name = "mayoristas/revision.html"
    permission_required = PERMISO_VER
    context_object_name = "solicitud"

    def get_object(self, queryset=None):
        solicitud = selectors.solicitud_para_revision(self.kwargs["pk"])
        if solicitud is None:
            raise Http404("La solicitud no existe.")
        return solicitud

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        solicitud = contexto["solicitud"]
        puede_gestionar = self.request.user.has_perm(PERMISO_GESTIONAR)
        contexto.update(
            {
                "puede_gestionar": puede_gestionar,
                "puede_decidir": (
                    puede_gestionar
                    and solicitud.estado == SolicitudMayorista.Estado.PENDIENTE
                ),
                "form_rechazo": RechazoSolicitudForm(),
                # La cola, corta: tras decidir se sigue con la siguiente sin
                # volver a la bandeja (el POST redirige aquí mismo).
                "solicitudes": self._cola(solicitud),
                "estado_filtro": "",
                "busqueda": "",
                "breadcrumbs": _migas_bandeja(solicitud.nombre_comercial),
            }
        )
        return contexto

    @staticmethod
    def _cola(solicitud, limite=8):
        """Las demás solicitudes pendientes, la más antigua primero."""
        return (
            SolicitudMayorista.objects.filter(
                estado=SolicitudMayorista.Estado.PENDIENTE
            )
            .exclude(pk=solicitud.pk)
            .select_related("usuario")
            .order_by("creado_en")[:limite]
        )


def _ficha_con_error(request, solicitud, formulario, estado_http=400):
    """Vuelve a pintar la ficha con el error del rechazo junto al campo."""
    return render(
        request,
        "mayoristas/revision.html",
        {
            "solicitud": solicitud,
            "puede_gestionar": True,
            "puede_decidir": solicitud.estado == SolicitudMayorista.Estado.PENDIENTE,
            "form_rechazo": formulario,
            "solicitudes": DetalleSolicitudView._cola(solicitud),
            "estado_filtro": "",
            "busqueda": "",
            "breadcrumbs": _migas_bandeja(solicitud.nombre_comercial),
        },
        status=estado_http,
    )


class AprobarSolicitudView(BandejaPermissionMixin, View):
    """POST que aprueba una solicitud. Cualquier otro método: 405 (DEC-06)."""

    permission_required = PERMISO_GESTIONAR
    http_method_names = ["post"]

    def post(self, request, pk):
        solicitud = selectors.solicitud_para_revision(pk)
        if solicitud is None:
            raise Http404("La solicitud no existe.")
        try:
            aprobar_solicitud(solicitud, revisor=request.user)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(
                request,
                f"Aprobaste la solicitud de {solicitud.nombre_comercial}. "
                "Le enviamos el aviso a su correo.",
            )
        return redirect("mayoristas:revision", pk=pk)


class RechazarSolicitudView(BandejaPermissionMixin, View):
    """POST que rechaza una solicitud con motivo. Cualquier otro método: 405."""

    permission_required = PERMISO_GESTIONAR
    http_method_names = ["post"]

    def post(self, request, pk):
        solicitud = selectors.solicitud_para_revision(pk)
        if solicitud is None:
            raise Http404("La solicitud no existe.")

        formulario = RechazoSolicitudForm(request.POST)
        if not formulario.is_valid():
            return _ficha_con_error(request, solicitud, formulario)

        try:
            rechazar_solicitud(
                solicitud,
                revisor=request.user,
                motivo=formulario.cleaned_data["motivo"],
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(
                request,
                f"Rechazaste la solicitud de {solicitud.nombre_comercial}. "
                "Le enviamos el motivo a su correo.",
            )
        return redirect("mayoristas:revision", pk=pk)


# ═══════════════════════════════════════════════════════════════════════
# VM-03 (JODS-97) · Catálogo mayorista
# ═══════════════════════════════════════════════════════════════════════
#
# Solo entra quien tiene acceso B2B: rol MAYORISTA aprobado o administración.
# Un CLIENTE no ve precios de referencia ni la existencia del catálogo: recibe
# 403, no un catálogo vacío, para que no parezca que la tienda está sin
# producto.
#
# DEC-03: CADA precio que se enseña va acompañado de «Precio de referencia —
# sujeto a cotización». No es un detalle de diseño: es la regla de negocio.

class AccesoMayoristaMixin(LoginRequiredMixin):
    """Exige sesión y acceso B2B (rol MAYORISTA o cuenta de administración).

    Se comprueba con `rol_efectivo`, que ya resuelve el caso del superusuario
    creado con `createsuperuser` (queda en CLIENTE pero cuenta como ADMIN).
    """

    raise_exception = False
    permission_denied_message = (
        "Esta sección es solo para cuentas mayoristas aprobadas."
    )

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.rol_efectivo not in ("MAYORISTA", "ADMIN"):
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


class CatalogoMayoristaView(AccesoMayoristaMixin, TemplateView):
    """Listado de productos disponibles para mayoristas (DEC-01).

    El aviso de «Tramos pendientes de configuración» (DEC-18) se resuelve aquí
    y no en la plantilla: la plantilla no debe saber si hay tramos, solo
    pintar lo que recibe.
    """

    template_name = "mayoristas/catalogo.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        busqueda = self.request.GET.get("q", "").strip()
        productos = selectors.catalogo_mayorista(busqueda)
        from mayoristas import selectors as _selectors

        contexto.update(
            {
                "productos": productos,
                "busqueda": busqueda,
                "total": productos.count(),
                "tramos": _selectors.tramos_de_referencia(),
                "hay_tramos": _selectors.hay_tramos_configurados(),
                "breadcrumbs": _migas_bandeja("Catálogo mayorista"),
            }
        )
        return contexto