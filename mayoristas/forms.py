"""Formularios del canal B2B.

`SolicitudMayoristaForm` (VM-01, JODS-95) es el registro extendido del
mayorista. El NIT se normaliza y valida en el modelo; aquí se replica la
misma comprobación en `clean_nit` para que el mensaje aparezca junto al campo
del formulario y no como error general.
"""

from django import forms

from .models import MENSAJE_NIT, PATRON_NIT, normalizar_nit, SolicitudMayorista


class SolicitudMayoristaForm(forms.ModelForm):
    """Registro de una joyería o distribuidor que pide acceso al catálogo B2B."""

    class Meta:
        model = SolicitudMayorista
        fields = (
            "tipo_persona",
            "nit",
            "nombre_comercial",
            "representante_legal",
            "ciudad",
            "telefono",
            "correo",
            "canal_venta",
            "referido",
        )
        labels = {
            "tipo_persona": "Tipo de persona",
            "nit": "NIT o cédula",
            "nombre_comercial": "Nombre comercial",
            "representante_legal": "Representante legal",
            "ciudad": "Ciudad",
            "telefono": "Teléfono",
            "correo": "Correo de contacto",
            "canal_venta": "¿Dónde vende?",
            "referido": "¿Quién te refirió?",
        }
        help_texts = {
            "tipo_persona": "Elige «Empresa» si compras con NIT y «Persona natural» si es con cédula.",
            "nit": "Solo números. Si tiene dígito de verificación, escríbelo con guion. Los puntos no hacen falta.",
            "representante_legal": "Nombre completo de quien representa a la empresa.",
            "correo": "Aquí recibirás el resultado de tu solicitud.",
            "canal_venta": "Opcional. Tienda física, redes sociales, ferias…",
            "referido": "Opcional. Persona o negocio que te recomendó.",
        }
        widgets = {
            "nit": forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}),
            "telefono": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"}),
            "correo": forms.EmailInput(attrs={"autocomplete": "email"}),
            "nombre_comercial": forms.TextInput(attrs={"autocomplete": "organization"}),
            "ciudad": forms.TextInput(attrs={"autocomplete": "address-level2"}),
        }

    def clean_nit(self):
        """Devuelve el NIT en su forma canónica ("900123456-7").

        Se acepta escrito con puntos y espacios; lo que se guarda y lo que se
        compara contra la restricción de unicidad es siempre el valor limpio.
        """
        valor = normalizar_nit(self.cleaned_data.get("nit"))
        if not PATRON_NIT.match(valor):
            raise forms.ValidationError(MENSAJE_NIT, code="nit_invalido")
        return valor


# ═══════════════════════════════════════════════════════════════════════
# VM-02 (JODS-96) · Rechazo con motivo
# ═══════════════════════════════════════════════════════════════════════

class RechazoSolicitudForm(forms.Form):
    """Motivo del rechazo, obligatorio.

    Es un `forms.Form` y no un `ModelForm` a propósito: el rechazo no «edita»
    la solicitud, la decide. Que el formulario no conozca el modelo impide que
    alguien envíe campos extra y termine cambiando otra cosa que no sea el
    motivo (el estado y el revisor los pone el servicio).
    """

    motivo = forms.CharField(
        label="Motivo del rechazo",
        max_length=500,
        # Mensaje propio: «Este campo es obligatorio» no explica que el texto
        # lo va a leer el cliente y por eso se exige.
        error_messages={
            "required": (
                "Escribe el motivo del rechazo: el cliente lo verá y podrá "
                "corregir lo que haga falta."
            )
        },
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "maxlength": 500,
                "placeholder": (
                    "Explica qué debe corregir la persona para volver a solicitar. "
                    "Este texto le llega por correo."
                ),
            }
        ),
        help_text=(
            "Lo que escribas aquí lo va a leer quien solicitó. Sé concreto: "
            "qué falta o qué debe corregir."
        ),
    )

    def clean_motivo(self):
        """El motivo no puede ser solo espacios en blanco."""
        valor = (self.cleaned_data.get("motivo") or "").strip()
        if not valor:
            raise forms.ValidationError(
                "Escribe el motivo del rechazo: el cliente lo verá.",
                code="motivo_vacio",
            )
        return valor
