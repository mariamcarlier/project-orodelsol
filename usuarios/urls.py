from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("perfil/", views.perfil, name="perfil"),
    path("perfil/editar/", views.editar_perfil, name="editar_perfil"),
    path("cuenta/<slug:clave>/", views.seccion_cuenta, name="seccion_cuenta"),
]