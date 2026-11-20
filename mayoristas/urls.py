from django.urls import path

from . import views

app_name = "mayoristas"

urlpatterns = [
    path("solicitar/", views.solicitar_acceso, name="solicitar_acceso"),
    path("solicitud/", views.mi_solicitud, name="mi_solicitud"),
]
