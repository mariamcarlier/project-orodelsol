from django import forms

from django.contrib.auth import authenticate, get_user_model

from allauth.account.forms import SignupForm
from django import forms
from django.contrib.auth import get_user_model

from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils.crypto import salted_hmac

from .models import Usuario


LOGIN_MAX_ATTEMPTS = 5
LOGIN_ATTEMPT_WINDOW = 15 * 60


class RateLimitedAuthenticationForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Correo electrónico o contraseña incorrectos.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        password_field = self.fields["password"]
        self.fields = {
            "email": forms.EmailField(
                label="Correo electrónico",
                widget=forms.EmailInput(
                    attrs={"autofocus": True, "autocomplete": "email"}
                ),
            ),
            "password": password_field,
        }

    def clean(self):
        email = self.cleaned_data.get("email")
        password = self.cleaned_data.get("password")
        if not email or not password:
            return self.cleaned_data

        user_model = get_user_model()
        email_matches = user_model.objects.filter(email__iexact=username)
        if email_matches.count() == 1:
            self.cleaned_data["username"] = email_matches.get().get_username()

        remote_addr = self.request.META.get("REMOTE_ADDR", "")
        cache_key = "login-attempts:" + salted_hmac(
            "usuarios.login_attempts",
            f"{email.casefold()}\0{remote_addr}",
        ).hexdigest()

        if cache.get(cache_key, 0) >= LOGIN_MAX_ATTEMPTS:
            raise ValidationError(
                "Demasiados intentos fallidos. Espera 15 minutos antes de volver a intentar.",
                code="too_many_attempts",
            )

        try:
            UserModel = get_user_model()
            try:
                usuario = UserModel._default_manager.get(email__iexact=email)
            except (UserModel.DoesNotExist, UserModel.MultipleObjectsReturned):
                usuario = None

            self.user_cache = (
                authenticate(
                    self.request,
                    username=usuario.get_username(),
                    password=password,
                )
                if usuario
                else None
            )
            if self.user_cache is None:
                raise ValidationError(
                    self.error_messages["invalid_login"],
                    code="invalid_login",
                )
            self.confirm_login_allowed(self.user_cache)
            cleaned_data = self.cleaned_data
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in (
            "first_name",
            "last_name",
            "tipo_documento",
            "documento",
            "fecha_nacimiento",
            "telefono",
        ):
            self.fields[field_name].required = True

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and Usuario.objects.filter(email__iexact=email).exclude(
            pk=self.instance.pk
        ).exists():
            raise forms.ValidationError("Ya existe un usuario registrado con este correo electrónico.")
        return email.lower() if email else email


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
class AllauthCrearCuentaForm(SignupForm):
    first_name = forms.CharField(
        label="Nombre",
        max_length=50,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "given-name",
                "placeholder": "Tu nombre",
            }
        ),
    )
    field_order = ["first_name", "email", "password1"]

    def clean_first_name(self):
        return " ".join(self.cleaned_data["first_name"].split())


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

            "groups": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in (
            "first_name",
            "last_name",
            "tipo_documento",
            "documento",
            "fecha_nacimiento",
            "telefono",
        ):
            self.fields[field_name].required = True


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
        for field_name in (
            "first_name",
            "last_name",
            "tipo_documento",
            "documento",
            "fecha_nacimiento",
            "telefono",
        ):
            self.fields[field_name].required = True
        if self.instance and self.instance.fecha_nacimiento:
            self.initial["fecha_nacimiento"] = self.instance.fecha_nacimiento.isoformat()