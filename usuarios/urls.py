from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("registrar/", views.registrar_usuario, name="registrar_usuario"),
    path("perfil/", views.perfil, name="perfil"),
    path("perfil/editar/", views.editar_perfil, name="editar_perfil"),
]
