from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = "core"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="iniciar_sesion",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="cerrar_sesion",
    ),
    path("panel-admin/", views.admin_dashboard, name="admin_dashboard"),
    path(
        "panel-admin/<str:seccion>/",
        views.admin_section,
        name="admin_section",
    ),
    path("productos/", views.producto_listar, name="producto_listar"),
    path("productos/nuevo/", views.producto_guardar, name="producto_crear"),
    path("productos/<int:pk>/editar/", views.producto_guardar, name="producto_editar"),
    path("productos/<int:pk>/eliminar/", views.producto_eliminar, name="producto_eliminar"),
    path("colecciones/", views.ColeccionListView.as_view(), name="coleccion_listar"),
    path(
        "colecciones/nueva/",
        views.ColeccionCreateView.as_view(),
        name="coleccion_crear",
    ),
    path(
        "colecciones/<int:pk>/editar/",
        views.ColeccionUpdateView.as_view(),
        name="coleccion_editar",
    ),
    path(
        "colecciones/<int:pk>/eliminar/",
        views.ColeccionDeleteView.as_view(),
        name="coleccion_eliminar",
    ),
]
