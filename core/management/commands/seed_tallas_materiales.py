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

# 4.0, 4.5, ... 13.0
TALLAS_US = [Decimal(n) / 2 for n in range(8, 27)]


class Command(BaseCommand):
    help = "Carga tallas US y materiales base (idempotente)."

    @transaction.atomic
    def handle(self, *args, **options):
        materiales_nuevos = 0
        for nombre in MATERIALES:
            _, creado = Material.objects.get_or_create(nombre=nombre)
            materiales_nuevos += creado

        tallas_nuevas = 0
        for talla_us in TALLAS_US:
            _, creada = Talla.objects.get_or_create(talla_us=talla_us)
            tallas_nuevas += creada

        self.stdout.write(
            self.style.SUCCESS(
                f"Materiales: {materiales_nuevos} nuevos de {len(MATERIALES)}. "
                f"Tallas: {tallas_nuevas} nuevas de {len(TALLAS_US)}."
            )
        )
