"""
URL configuration for app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.views.generic import RedirectView
from configuracion import views as configuracion_views

admin.site.site_header = "Administración de Oro del Sol"
admin.site.site_title = "Oro del Sol"
admin.site.index_title = "Gestión de la tienda"

urlpatterns = [
    path("admin/configuracion/", configuracion_views.parametros_view),
    path(
        "admin/",
        RedirectView.as_view(pattern_name="core:admin_dashboard", permanent=False),
        name="admin-dashboard-home",
    ),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("core.urls", namespace="core")),
    path("configuracion/", include("configuracion.urls")),
    path("usuario/", include("usuarios.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
