from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("panel-admin/", views.admin_dashboard, name="admin_dashboard"),
    path(
        "panel-admin/<str:seccion>/",
        views.admin_section,
        name="admin_section",
    ),
]
