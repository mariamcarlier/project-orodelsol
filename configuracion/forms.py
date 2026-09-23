# ═══════════════════════════════════════════════════════════════
# forms.py — Formularios del módulo Configuración
#
# ¿Por qué existe este archivo?
# Con CBV (CreateView), Django generaba el formulario automáticamente
# a partir del campo 'fields'. Con FBV, nosotros definimos
# explícitamente qué campos se muestran y cómo se validan.
#
# ModelForm: genera un formulario HTML a partir de un modelo de BD.
# ═══════════════════════════════════════════════════════════════

from django import forms
from .models import Impuesto, Moneda


class ImpuestoForm(forms.ModelForm):
    class Meta:
        model  = Impuesto
        fields = ['nombre', 'tasa', 'vigente']

        # Textos de ayuda visibles debajo de cada campo en el HTML
        help_texts = {
            'nombre':  'Ej: IVA 19%',
            'tasa':    'Porcentaje numérico. Ej: 19.00',
            'vigente': 'Desmarca si el impuesto ya no aplica.',
        }


class MonedaForm(forms.ModelForm):
    class Meta:
        model  = Moneda
        fields = ['codigo_iso', 'nombre', 'simbolo', 'tasa_cambio', 'es_principal', 'activa']

        help_texts = {
            'codigo_iso':   'Código ISO 4217 en mayúsculas. Ej: COP, USD, EUR',
            'nombre':       'Nombre completo de la moneda. Ej: Peso colombiano',
            'simbolo':      'Símbolo corto. Ej: $, €, £',
            'tasa_cambio':  'Tasa respecto a la moneda principal. La principal siempre vale 1.0000',
            'es_principal': 'Al activar esto, la moneda principal anterior se desmarcará automáticamente.',
            'activa':       'Las monedas inactivas no se ofrecen al usuario.',
        }
