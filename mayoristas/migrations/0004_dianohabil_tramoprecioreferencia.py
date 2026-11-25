from django.db import migrations, models


class Migration(migrations.Migration):
    """Crea los tramos de referencia y el calendario de días no hábiles.

    VM-16 (JODS-110) y RN-VM-06. Solo añade dos tablas nuevas: no toca
    ninguna existente, ni datos, ni restricciones de `SolicitudMayorista`.

    Ambas nacen VACÍAS a propósito:

    - `TramoPrecioReferencia`: DEC-02 pide que los tramos sean configurables en
      la base de datos y prohíbe inventar porcentajes. El campo `porcentaje`
      admite NULL y el sistema no calcula nada mientras siga vacío (DEC-18).
    - `DiaNoHabil`: los festivos colombianos cambian cada año y los decide el
      negocio. Sin calendario cargado, el SLA solo descuenta fines de semana.
    """

    dependencies = [
        ('mayoristas', '0003_alter_solicitudmayorista_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='DiaNoHabil',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(unique=True, verbose_name='fecha')),
                ('nombre', models.CharField(help_text='Por ejemplo «Día de la Independencia» o «Cierre por inventario».', max_length=120, verbose_name='nombre')),
            ],
            options={
                'verbose_name': 'día no hábil',
                'verbose_name_plural': 'días no hábiles',
                'ordering': ('fecha',),
            },
        ),
        migrations.CreateModel(
            name='TramoPrecioReferencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(help_text='Cómo lo verá el equipo en el panel, por ejemplo «Medio mayorista».', max_length=60, verbose_name='nombre del tramo')),
                ('cantidad_minima', models.PositiveIntegerField(help_text='Desde cuántas unidades aplica el tramo.', verbose_name='cantidad mínima')),
                ('cantidad_maxima', models.PositiveIntegerField(blank=True, help_text='Hasta cuántas unidades aplica. Déjalo vacío para «sin límite» (el tramo de 60 o más).', null=True, verbose_name='cantidad máxima')),
                ('porcentaje', models.DecimalField(blank=True, decimal_places=2, help_text='Porcentaje que se muestra como referencia sobre el precio. Déjalo vacío mientras no esté definido: sin porcentaje no se calcula nada y no se inventa ninguna cifra.', max_digits=5, null=True, verbose_name='porcentaje de referencia')),
                ('activo', models.BooleanField(default=True, verbose_name='activo')),
                ('creado_en', models.DateTimeField(auto_now_add=True, verbose_name='creado en')),
            ],
            options={
                'verbose_name': 'tramo de precio de referencia',
                'verbose_name_plural': 'tramos de precio de referencia',
                'ordering': ('cantidad_minima',),
                'constraints': [models.CheckConstraint(condition=models.Q(('cantidad_minima__gte', 1)), name='tramo_cantidad_minima_positiva'), models.CheckConstraint(condition=models.Q(('cantidad_maxima__isnull', True), ('cantidad_maxima__gte', models.F('cantidad_minima')), _connector='OR'), name='tramo_rango_coherente'), models.CheckConstraint(condition=models.Q(('porcentaje__isnull', True), models.Q(('porcentaje__gte', 0), ('porcentaje__lte', 100)), _connector='OR'), name='tramo_porcentaje_valido')],
            },
        ),
    ]