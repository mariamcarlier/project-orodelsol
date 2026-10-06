from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "rol",
        "is_active",
        "is_staff",
    )
    list_filter = ("rol", "is_active", "is_staff", "is_superuser", "groups")
    search_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
        "documento",
        "telefono",
    )
    ordering = ("username",)
    filter_horizontal = ("groups", "user_permissions")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Datos personales",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "tipo_documento",
                    "documento",
                    "fecha_nacimiento",
                    "telefono",
                    "foto",
                    "rol",
                )
            },
        ),
        (
            "Acceso y permisos",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "password1",
                    "password2",
                    "email",
                    "first_name",
                    "last_name",
                    "tipo_documento",
                    "documento",
                    "fecha_nacimiento",
                    "telefono",
                    "rol",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )
    actions = ("activar_usuarios", "desactivar_usuarios")

    @admin.action(description="Activar usuarios seleccionados")
    def activar_usuarios(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Desactivar usuarios seleccionados")
    def desactivar_usuarios(self, request, queryset):
        queryset.update(is_active=False)
