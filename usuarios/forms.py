from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Usuario

class RegistroUsuarioForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = [
            "username", "email", "first_name", "last_name",
            "tipo_documento", "documento", "fecha_nacimiento", "rol",
        ]

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe un usuario registrado con este correo electrónico.")
        return email


class EditarPerfilForm(forms.ModelForm):
    """
    USR-07 - Editar perfil.
    Reutiliza las validaciones definidas en el modelo Usuario.
    """

    class Meta:
        model = Usuario
        fields = [
            "first_name",
            "last_name",
            "email",
            "tipo_documento",
            "documento",
            "fecha_nacimiento",
            "telefono",
            "foto",
        ]
        widgets = {
            "fecha_nacimiento": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
        }
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "Correo electrónico",
            "tipo_documento": "Tipo de documento",
            "documento": "Número de documento",
            "fecha_nacimiento": "Fecha de nacimiento",
            "telefono": "Teléfono",
            "foto": "Foto de perfil",
        }
        error_messages = {
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