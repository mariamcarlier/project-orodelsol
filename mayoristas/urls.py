from django.urls import path

from . import views

app_name = "mayoristas"

urlpatterns = [
    # ── VM-01 (JODS-95): el cliente pide acceso y consulta su estado ──
    path("solicitar/", views.solicitar_acceso, name="solicitar_acceso"),
    path("solicitud/", views.mi_solicitud, name="mi_solicitud"),
    # ── VM-02 (JODS-96): el equipo revisa y decide ──
    # La bandeja se llama «bandeja» y no «solicitudes» para no confundirla con
    # «solicitud/» (la del propio cliente).
    path("bandeja/", views.BandejaSolicitudesView.as_view(), name="bandeja"),
    path(
        "bandeja/<int:pk>/",
        views.DetalleSolicitudView.as_view(),
        name="revision",
    ),
    path(
        "bandeja/<int:pk>/aprobar/",
        views.AprobarSolicitudView.as_view(),
        name="aprobar",
    ),
    path(
        "bandeja/<int:pk>/rechazar/",
        views.RechazarSolicitudView.as_view(),
        name="rechazar",
    ),
    # ── VM-03 (JODS-97): catálogo mayorista ──
    path(
        "catalogo/",
        views.CatalogoMayoristaView.as_view(),
        name="catalogo",
    ),
]
