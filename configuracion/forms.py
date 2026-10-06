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
from .models import Impuesto, Moneda, Idioma, ParametroGeneral


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


class IdiomaForm(forms.ModelForm):
    class Meta:
        model  = Idioma
        fields = ['codigo', 'nombre', 'es_principal', 'activo']

        help_texts = {
            'codigo':       'Código estándar del idioma. Ej: es, en, fr, pt',
            'nombre':       'Nombre descriptivo del idioma. Ej: Español, English',
            'es_principal': 'Al marcar este idioma como principal, el anterior se desmarcará automáticamente.',
            'activo':       'Los idiomas inactivos no se ofrecen a los usuarios en la tienda.',
        }


class ParametroGeneralForm(forms.ModelForm):
    class Meta:
        model = ParametroGeneral
        fields = [
            'nombre_tienda',
            'lema',
            'nit',
            'correo_contacto',
            'telefono_contacto',
            'direccion',
            'ciudad',
            'horario_atencion',
        ]
        help_texts = {
            'nombre_tienda':     'Nombre oficial de la joyería.',
            'lema':              'Frase distintiva o descripción corta de la marca.',
            'nit':               'Número de Identificación Tributaria (NIT/RUT).',
            'correo_contacto':   'Correo donde los clientes y el sistema envían notificaciones.',
            'telefono_contacto': 'Teléfono o línea WhatsApp de atención al cliente.',
            'direccion':         'Ubicación física del showroom o sede comercial.',
            'ciudad':            'Ciudad y país principal donde opera la joyería.',
            'horario_atencion':  'Horarios y días hábiles de atención al público.',
        }


