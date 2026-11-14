"""Carga tallas, materiales y piedras base. Idempotente: puede correrse N veces.

Solo crea lo que no existe (get_or_create); nunca modifica ni borra filas ya
editadas desde el admin.

- Materiales: solo los confirmados por el negocio (hoy, oro amarillo 18K).
- Piedras: las 9 referencias de la tabla de colores de la empresa (A–I).
- Tallas: numeración US de 4 a 13 en pasos de media talla. El rango es un
  supuesto por confirmar: edita TALLAS_US y vuelve a correr el comando.
- Diámetro interior: NO se carga. Queda vacío y sin verificar hasta que se
  mida y se valide físicamente (no se calcula ni se inventa).
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Material, Piedra, Talla

MATERIALES = ["Oro amarillo 18K"]

# Tabla de referencias de colores de la empresa.
PIEDRAS = [
    {"ref": "A", "nombre": "Cristal", "imagen": "img/piedras/A-Cristal.webp"},
    {"ref": "B", "nombre": "Azul Hielo", "imagen": "img/piedras/B-Azul-Hielo.webp"},
    {"ref": "C", "nombre": "Verde", "imagen": "img/piedras/C-Verde.webp"},
    {"ref": "D", "nombre": "Verde oscuro", "imagen": "img/piedras/D-Verde-Oscuro.webp"},
    {"ref": "E", "nombre": "Verde oliva", "imagen": "img/piedras/E-Verde-Oliva.webp"},
    {"ref": "F", "nombre": "Rosado claro", "imagen": "img/piedras/F-RosaClaro.webp"},
    {"ref": "G", "nombre": "Rosado", "imagen": "img/piedras/G-Rosado.webp"},
    {"ref": "H", "nombre": "Fucsia", "imagen": "img/piedras/H-Fucsia.webp"},
    {"ref": "I", "nombre": "Naranja", "imagen": "img/piedras/I-Naranja.webp"},
]

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
    help = "Carga tallas US, materiales y piedras base (idempotente)."

    @transaction.atomic
    def handle(self, *args, **options):
        materiales_nuevos = 0
        for nombre in MATERIALES:
            _, creado = Material.objects.get_or_create(nombre=nombre)
            materiales_nuevos += creado

        piedras_nuevas = 0
        for orden, piedra in enumerate(PIEDRAS, start=1):
            _, creada = Piedra.objects.get_or_create(
                ref=piedra["ref"],
                defaults={
                    "nombre": piedra["nombre"],
                    "imagen": piedra["imagen"],
                    "orden": orden,
                },
            )
            piedras_nuevas += creada

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
                f"Piedras: {piedras_nuevas} nuevas de {len(PIEDRAS)}. "
                f"Tallas: {tallas_nuevas} nuevas de {len(TALLAS_DATA)}."
            )
        )