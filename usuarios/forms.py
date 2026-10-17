from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils.crypto import salted_hmac

from .models import Usuario


LOGIN_MAX_ATTEMPTS = 5
LOGIN_ATTEMPT_WINDOW = 15 * 60


class RateLimitedAuthenticationForm(AuthenticationForm):
    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if not username or not password:
            return super().clean()

        remote_addr = self.request.META.get("REMOTE_ADDR", "")
        cache_key = "login-attempts:" + salted_hmac(
            "usuarios.login_attempts",
            f"{username.casefold()}\0{remote_addr}",
        ).hexdigest()

        if cache.get(cache_key, 0) >= LOGIN_MAX_ATTEMPTS:
            raise ValidationError(
                "Demasiados intentos fallidos. Espera 15 minutos antes de volver a intentar.",
                code="too_many_attempts",
            )

        try:
            cleaned_data = super().clean()
        except ValidationError:
            if not cache.add(
                cache_key,
                1,
                timeout=LOGIN_ATTEMPT_WINDOW,
            ):
                try:
                    cache.incr(cache_key)
                except ValueError:
                    cache.add(
                        cache_key,
                        1,
                        timeout=LOGIN_ATTEMPT_WINDOW,
                    )
            raise

        if self.get_user() is not None:
            cache.delete(cache_key)
        return cleaned_data


class RegistroUsuarioForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = [  # noqa: RUF012
            "username", "email", "first_name", "last_name",
            "tipo_documento", "documento", "fecha_nacimiento", "telefono", "rol",
        ]

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe un usuario registrado con este correo electrónico.")
        return email


class RegistroClienteForm(RegistroUsuarioForm):
    class Meta(RegistroUsuarioForm.Meta):
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "tipo_documento",
            "documento",
            "fecha_nacimiento",
            "telefono",
        )

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.rol = "CLIENTE"
        usuario.is_staff = False
        usuario.is_superuser = False
        if commit:
            usuario.save()
        return usuario


class AdministrarUsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [  # noqa: RUF012
            "first_name",
            "last_name",
            "email",
            "tipo_documento",
            "documento",
            "fecha_nacimiento",
            "telefono",
            "foto",
            "rol",
            "is_active",
            "is_staff",
            "groups",
        ]
        widgets = {  # noqa: RUF012
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
        }


class EditarPerfilForm(forms.ModelForm):
    """
    USR-07 - Editar perfil.
    Reutiliza las validaciones definidas en el modelo Usuario.
    """

    class Meta:
        model = Usuario
        fields = [  # noqa: RUF012
            "first_name",
            "last_name",
            "email",
            "tipo_documento",
            "documento",
            "fecha_nacimiento",
            "telefono",
            "foto",
        ]
        widgets = {  # noqa: RUF012
            "fecha_nacimiento": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
        }
        labels = {  # noqa: RUF012
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "Correo electrónico",
            "tipo_documento": "Tipo de documento",
            "documento": "Número de documento",
            "fecha_nacimiento": "Fecha de nacimiento",
            "telefono": "Teléfono",
            "foto": "Foto de perfil",
        }
        error_messages = {  # noqa: RUF012
            "first_name": {"required": "El nombre es obligatorio."},
            "last_name": {"required": "El apellido es obligatorio."},
            "documento": {
                "required": "El número de documento es obligatorio.",
                "unique": "Ya existe otro usuario registrado con este documento.",
            },
            "fecha_nacimiento": {
                "required": "La fecha de nacimiento es obligatoria.",
                "invalid": "Ingresa una fecha válida.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.fecha_nacimiento:
            self.initial["fecha_nacimiento"] = self.instance.fecha_nacimiento.isoformat()