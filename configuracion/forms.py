# Formularios compartidos por las secciones de configuración del panel.

from django import forms


from .models import CostoEnvio, Idioma, Impuesto, Moneda, ParametroGeneral

import re
from .models import CostoEnvio, Idioma, Impuesto, MetodoPago, Moneda, ParametroGeneral, PoliticaComercial



class ImpuestoForm(forms.ModelForm):
    class Meta:
        model  = Impuesto
        fields = ['nombre', 'tasa', 'vigente']  # noqa: RUF012

        # Textos de ayuda visibles debajo de cada campo en el HTML
        help_texts = {  # noqa: RUF012
            'nombre':  'Ej: IVA 19%',
            'tasa':    'Porcentaje numérico. Ej: 19.00',
            'vigente': 'Desmarca si el impuesto ya no aplica.',
        }


class MonedaForm(forms.ModelForm):
    class Meta:
        model  = Moneda
        fields = ['codigo_iso', 'nombre', 'simbolo', 'tasa_cambio', 'es_principal', 'activa']  # noqa: RUF012

        help_texts = {  # noqa: RUF012
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
        fields = ['codigo', 'nombre', 'es_principal', 'activo']  # noqa: RUF012

        help_texts = {  # noqa: RUF012
            'codigo':       'Código estándar del idioma. Ej: es, en, fr, pt',
            'nombre':       'Nombre descriptivo del idioma. Ej: Español, English',
            'es_principal': 'Al marcar este idioma como principal, el anterior se desmarcará automáticamente.',
            'activo':       'Los idiomas inactivos no se ofrecen a los usuarios en la tienda.',
        }


class ParametroGeneralForm(forms.ModelForm):
    class Meta:
        model = ParametroGeneral
        fields = [  # noqa: RUF012
            'nombre_tienda',
            'lema',
            'nit',
            'correo_contacto',
            'telefono_contacto',
            'direccion',
            'ciudad',
            'horario_atencion',
        ]
        help_texts = {  # noqa: RUF012
            'nombre_tienda':     'Nombre oficial de la joyería.',
            'lema':              'Frase distintiva o descripción corta de la marca.',
            'nit':               'Número de Identificación Tributaria (NIT/RUT).',
            'correo_contacto':   'Correo donde los clientes y el sistema envían notificaciones.',
            'telefono_contacto': 'Teléfono o línea WhatsApp de atención al cliente.',
            'direccion':         'Ubicación física del showroom o sede comercial.',
            'ciudad':            'Ciudad y país principal donde opera la joyería.',
            'horario_atencion':  'Horarios y días hábiles de atención al público.',
        }




class CostoEnvioForm(forms.ModelForm):
    class Meta:
        model = CostoEnvio
        fields = [  # noqa: RUF012
            "ciudad",
            "departamento",
            "precio",
            "tiempo_entrega",
            "activo",
        ]
        help_texts = {  # noqa: RUF012
            "ciudad": "Nombre de la ciudad o municipio de destino.",
            "departamento": "Departamento o región de destino.",
            "precio": "Valor en COP. Debe ser cero o un valor positivo.",
            "tiempo_entrega": "Ejemplo: 2 a 4 días hábiles. Confirma el plazo antes de publicarlo.",
            "activo": "Solo las tarifas activas deben considerarse para futuras consultas del checkout.",
        }

    def clean_precio(self):
        precio = self.cleaned_data["precio"]
        if precio < 0:
            raise forms.ValidationError("El costo de envío no puede ser negativo.")
        return precio


class MetodoPagoForm(forms.ModelForm):
    class Meta:
        model = MetodoPago
        fields = [
            "nombre",
            "tipo",
            "banco",
            "tipo_cuenta",
            "numero_cuenta",
            "titular",
            "documento_titular",
            "instrucciones",
            "activo",
            "orden",
        ]
        help_texts = {
            "nombre": "Nombre comercial o etiqueta visible en checkout (ej: Bancolombia Transferencia, Nequi).",
            "tipo": "Tipo de método de pago manual (enfoque en transferencias con validación de comprobante).",
            "banco": "Entidad bancaria o billetera (requerido para transferencias bancarias).",
            "tipo_cuenta": "Tipo de cuenta o billetera digital.",
            "numero_cuenta": "Número de cuenta o celular asociado.",
            "titular": "Nombre completo o razón social del titular.",
            "documento_titular": "NIT o cédula del titular.",
            "instrucciones": "Instrucciones de pago y envío de comprobante (WhatsApp, correo, etc.).",
            "activo": "Marca para que esté disponible para selección de los clientes en checkout.",
            "orden": "Posición en la lista de opciones (0 aparece primero).",
        }

    def clean_numero_cuenta(self):
        numero = self.cleaned_data.get("numero_cuenta", "").strip()
        if numero and not re.match(r"^[\d\s\-]+$", numero):
            raise forms.ValidationError(
                "El número de cuenta solo debe contener dígitos, guiones o espacios."
            )
        return numero

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get("tipo")
        banco = (cleaned_data.get("banco") or "").strip()
        numero_cuenta = (cleaned_data.get("numero_cuenta") or "").strip()
        titular = (cleaned_data.get("titular") or "").strip()

        if tipo in {"TRANSFERENCIA", "NEQUI", "DAVIPLATA"}:
            if not numero_cuenta:
                self.add_error(
                    "numero_cuenta",
                    "El número de cuenta o celular es obligatorio para transferencias y billeteras.",
                )
            if not titular:
                self.add_error(
                    "titular",
                    "El nombre del titular es obligatorio para transferencias y billeteras.",
                )
            if tipo == "TRANSFERENCIA" and not banco:
                self.add_error(
                    "banco",
                    "Debes indicar la entidad bancaria para transferencias.",
                )
            elif tipo == "NEQUI" and not banco:
                cleaned_data["banco"] = "Nequi"
            elif tipo == "DAVIPLATA" and not banco:
                cleaned_data["banco"] = "Daviplata"

        return cleaned_data


class PoliticaComercialForm(forms.ModelForm):
    class Meta:
        model = PoliticaComercial
        fields = [
            "monto_minimo_compra_b2c",
            "monto_minimo_compra_b2b",
            "monto_minimo_envio_gratis",
            "tiempo_reserva_carrito_minutos",
            "vigencia_cupones_dias",
        ]
        help_texts = {
            "monto_minimo_compra_b2c": "Monto mínimo requerido para procesar pedidos de clientes particulares (B2C). En COP. 0 indica sin mínimo.",
            "monto_minimo_compra_b2b": "Monto mínimo requerido para procesar pedidos de clientes mayoristas (B2B). En COP. 0 indica sin mínimo.",
            "monto_minimo_envio_gratis": "Monto de compra a partir del cual el costo de envío es $0 COP. 0 desactiva el beneficio.",
            "tiempo_reserva_carrito_minutos": "Tiempo en minutos que se reserva el inventario de una joya en el carrito.",
            "vigencia_cupones_dias": "Días de validez por defecto para cupones emitidos por la joyería.",
        }

    def clean_monto_minimo_compra_b2c(self):
        monto = self.cleaned_data.get("monto_minimo_compra_b2c")
        if monto is not None and monto < 0:
            raise forms.ValidationError("El monto mínimo de compra B2C no puede ser negativo.")
        return monto

    def clean_monto_minimo_compra_b2b(self):
        monto = self.cleaned_data.get("monto_minimo_compra_b2b")
        if monto is not None and monto < 0:
            raise forms.ValidationError("El monto mínimo de compra B2B no puede ser negativo.")
        return monto

    def clean_monto_minimo_envio_gratis(self):
        monto = self.cleaned_data.get("monto_minimo_envio_gratis")
        if monto is not None and monto < 0:
            raise forms.ValidationError("El monto mínimo para envío gratis no puede ser negativo.")
        return monto

    def clean_tiempo_reserva_carrito_minutos(self):
        tiempo = self.cleaned_data.get("tiempo_reserva_carrito_minutos")
        if tiempo is not None and tiempo < 1:
            raise forms.ValidationError("El tiempo de reserva de carrito debe ser de al menos 1 minuto.")
        return tiempo

    def clean_vigencia_cupones_dias(self):
        dias = self.cleaned_data.get("vigencia_cupones_dias")
        if dias is not None and dias < 1:
            raise forms.ValidationError("La vigencia de cupones debe ser de al menos 1 día.")
        return dias


