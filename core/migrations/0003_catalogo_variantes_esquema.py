"""Migración 1 de 3 (esquema).

Crea Talla, Material y VarianteProducto, y añade a Producto: `codigo`
(todavía NULLABLE, para no romper los productos existentes), `es_borrador`
y los M2M de tallas y materiales permitidos.

`es_borrador` nace en False: los productos ya publicados siguen visibles.
La 0004 rellena `codigo` y la 0005 lo vuelve único y obligatorio.
"""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_alter_coleccion_options_alter_producto_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='Talla',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('talla_us', models.DecimalField(decimal_places=1, max_digits=4, unique=True)),
                ('diametro_interno_mm', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('diametro_verificado', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name': 'talla',
                'verbose_name_plural': 'tallas',
                'ordering': ('talla_us',),
                'constraints': [
                    models.CheckConstraint(condition=Q(talla_us__gt=0), name='talla_us_positiva'),
                    models.CheckConstraint(
                        condition=Q(diametro_interno_mm__isnull=True) | Q(diametro_interno_mm__gt=0),
                        name='talla_diametro_positivo',
                    ),
                    models.CheckConstraint(
                        condition=Q(diametro_verificado=False) | Q(diametro_interno_mm__isnull=False),
                        name='talla_verificada_con_diametro',
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name='Material',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=60, unique=True)),
            ],
            options={
                'verbose_name': 'material',
                'verbose_name_plural': 'materiales',
                'ordering': ('nombre',),
            },
        ),
        migrations.AddField(
            model_name='producto',
            name='codigo',
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='producto',
            name='es_borrador',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='producto',
            name='tallas',
            field=models.ManyToManyField(blank=True, related_name='productos', to='core.talla', verbose_name='tallas permitidas'),
        ),
        migrations.AddField(
            model_name='producto',
            name='materiales',
            field=models.ManyToManyField(blank=True, related_name='productos', to='core.material', verbose_name='materiales permitidos'),
        ),
        migrations.CreateModel(
            name='VarianteProducto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sku', models.CharField(max_length=40, unique=True)),
                ('peso_gramos', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ('precio_adicional', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('stock', models.PositiveIntegerField(default=0)),
                ('activa', models.BooleanField(default=True)),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='variantes', to='core.material')),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='variantes', to='core.producto')),
                ('talla', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='variantes', to='core.talla')),
            ],
            options={
                'verbose_name': 'variante de producto',
                'verbose_name_plural': 'variantes de producto',
                'ordering': ('producto', 'talla'),
                'constraints': [
                    models.UniqueConstraint(fields=('producto', 'talla', 'material'), name='variante_unica'),
                    models.CheckConstraint(
                        condition=Q(peso_gramos__isnull=True) | Q(peso_gramos__gt=0),
                        name='variante_peso_positivo',
                    ),
                    models.CheckConstraint(
                        condition=Q(precio_adicional__gte=0),
                        name='variante_precio_adicional_no_negativo',
                    ),
                ],
            },
        ),
    ]
