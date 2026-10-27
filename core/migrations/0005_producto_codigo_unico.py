"""Migración 3 de 3 (restricciones).

`codigo` pasa a ÚNICO y NOT NULL. Solo es seguro después de la 0004: si algún
producto siguiera sin código, esta migración fallaría y la base se queda en la
0004 sin perder datos (se corrige con una migración nueva, no editando esta).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_asignar_codigo_productos'),
    ]

    operations = [
        migrations.AlterField(
            model_name='producto',
            name='codigo',
            field=models.CharField(blank=True, max_length=30, unique=True),
        ),
    ]
