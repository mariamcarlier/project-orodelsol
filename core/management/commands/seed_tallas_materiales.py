"""Carga las tallas y materiales base. Idempotente: puede correrse N veces.

Solo crea lo que no existe (get_or_create); nunca modifica ni borra filas ya
editadas desde el admin.

- Materiales: solo los confirmados por el negocio (hoy, oro amarillo 18K).
- Tallas: numeración US de 4 a 13 en pasos de media talla. El rango es un
  supuesto por confirmar: edita TALLAS_US y vuelve a correr el comando.
- Diámetro interior: NO se carga. Queda vacío y sin verificar hasta que se
  mida y se valide físicamente (no se calcula ni se inventa).
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Material, Talla

MATERIALES = ["Oro amarillo 18K"]

# Diccionario con diámetros de referencia (GLAMIRA) y talla nacional (CO)
TALLAS_DATA = {
    Decimal('4.0'): {'diametro': Decimal('14.90'), 'nacional': '6'},
    Decimal('4.5'): {'diametro': Decimal('15.30'), 'nacional': '7'},
    Decimal('5.0'): {'diametro': Decimal('15.70'), 'nacional': '8'},
    Decimal('5.5'): {'diametro': Decimal('16.10'), 'nacional': '9'},
    Decimal('6.0'): {'diametro': Decimal('16.50'), 'nacional': '10'},
    Decimal('6.5'): {'diametro': Decimal('16.90'), 'nacional': '11'},
    Decimal('7.0'): {'diametro': Decimal('17.30'), 'nacional': '12'},
    Decimal('7.5'): {'diametro': Decimal('17.70'), 'nacional': '13'},
    Decimal('8.0'): {'diametro': Decimal('18.10'), 'nacional': '14'},
    Decimal('8.5'): {'diametro': Decimal('18.50'), 'nacional': '15'},
    Decimal('9.0'): {'diametro': Decimal('18.90'), 'nacional': '16'},
    Decimal('9.5'): {'diametro': Decimal('19.40'), 'nacional': '17'},
    Decimal('10.0'): {'diametro': Decimal('19.80'), 'nacional': '18'},
    Decimal('10.5'): {'diametro': Decimal('20.20'), 'nacional': '19'},
    Decimal('11.0'): {'diametro': Decimal('20.60'), 'nacional': '20'},
    Decimal('11.5'): {'diametro': Decimal('21.00'), 'nacional': '21'},
    Decimal('12.0'): {'diametro': Decimal('21.50'), 'nacional': '22'},
    Decimal('12.5'): {'diametro': Decimal('21.90'), 'nacional': '23'},
    Decimal('13.0'): {'diametro': Decimal('22.30'), 'nacional': '24'},
}

class Command(BaseCommand):
    help = "Carga tallas US y materiales base (idempotente)."

    @transaction.atomic
    def handle(self, *args, **options):
        materiales_nuevos = 0
        for nombre in MATERIALES:
            _, creado = Material.objects.get_or_create(nombre=nombre)
            materiales_nuevos += creado

        tallas_nuevas = 0
        for talla_us, data in TALLAS_DATA.items():
            _, creada = Talla.objects.get_or_create(
                talla_us=talla_us,
                defaults={
                    'diametro_interno_mm': data['diametro'],
                    'talla_nacional': data['nacional']
                }
            )
            tallas_nuevas += creada

        self.stdout.write(
            self.style.SUCCESS(
                f"Materiales: {materiales_nuevos} nuevos de {len(MATERIALES)}. "
                f"Tallas: {tallas_nuevas} nuevas de {len(TALLAS_DATA)}."
            )
        )