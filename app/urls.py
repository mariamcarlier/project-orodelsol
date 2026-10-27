"""
URL configuration for app project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import urls as auth_urls
from django.contrib.auth.views import LoginView
from django.urls import include, path

from usuarios.forms import RateLimitedAuthenticationForm
from usuarios.views import crear_cuenta, perfil
from allauth.account.views import signup as allauth_signup

admin.site.site_header = "Administración de Oro del Sol"
admin.site.site_title = "Oro del Sol"
admin.site.index_title = "Gestión de la tienda"

auth_urlpatterns = [
    pattern for pattern in auth_urls.urlpatterns if pattern.name != "login"
]

urlpatterns = [
    path("configuracion/", include("configuracion.urls")),
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        LoginView.as_view(form_class=RateLimitedAuthenticationForm),
        name="login",
    ),
    path("accounts/", include(auth_urlpatterns)),
    path("", include("core.urls")),
    path("usuario/", include("usuarios.urls")),
    path("register/", allauth_signup, name="register"),
    path("accounts/", include("allauth.urls")),
    path("profile/", perfil, name="profile"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)