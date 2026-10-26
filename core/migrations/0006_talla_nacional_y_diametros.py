from decimal import Decimal

from django.db import migrations, models


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


def populate_tallas(apps, schema_editor):
    Talla = apps.get_model('core', 'Talla')
    for talla_us, data in TALLAS_DATA.items():
        Talla.objects.filter(talla_us=talla_us).update(
            diametro_interno_mm=data['diametro'],
            talla_nacional=data['nacional']
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_producto_codigo_unico'),
    ]

    operations = [
        migrations.AddField(
            model_name='talla',
            name='talla_nacional',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.RunPython(populate_tallas, migrations.RunPython.noop),
    ]