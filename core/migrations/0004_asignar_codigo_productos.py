"""Migración 2 de 3 (datos, idempotente).

Asigna `codigo` solo a los productos que no lo tienen (NULL; también cadena
vacía, que haría fallar la unicidad de la 0005). El contador arranca desde el
mayor AN-NNNN ya usado, nunca reinicia. Los códigos existentes no se tocan.

La función inversa no hace nada: quitar los códigos al revertir perdería
información y la 0003 ya los deja nullable.
"""

from django.db import migrations
from django.db.models import Q

PREFIJO = "AN-"


def asignar_codigos(apps, schema_editor):
    Producto = apps.get_model("core", "Producto")

    mayor = 0
    usados = (
        Producto.objects.exclude(codigo__isnull=True)
        .exclude(codigo="")
        .values_list("codigo", flat=True)
    )
    for codigo in usados:
        sufijo = codigo[len(PREFIJO):]
        if codigo.startswith(PREFIJO) and sufijo.isdigit():
            mayor = max(mayor, int(sufijo))

    pendientes = list(
        Producto.objects.filter(Q(codigo__isnull=True) | Q(codigo="")).order_by("pk")
    )
    for producto in pendientes:
        mayor += 1
        producto.codigo = f"{PREFIJO}{mayor:04d}"
        producto.save(update_fields=["codigo"])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_catalogo_variantes_esquema'),
    ]

    operations = [
        migrations.RunPython(asignar_codigos, migrations.RunPython.noop),
    ]
