import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mayoristas", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='solicitudmayorista',
            name='canal_venta',
            field=models.CharField(blank=True, help_text='Tienda física, redes sociales, ferias…', max_length=100, verbose_name='dónde vende'),
        ),
        migrations.AlterField(
            model_name='solicitudmayorista',
            name='ciudad',
            field=models.CharField(max_length=100, verbose_name='ciudad'),
        ),
        migrations.AlterField(
            model_name='solicitudmayorista',
            name='correo',
            field=models.EmailField(max_length=254, verbose_name='correo de contacto'),
        ),
        migrations.AlterField(
            model_name='solicitudmayorista',
            name='creado_en',
            field=models.DateTimeField(auto_now_add=True, verbose_name='creada en'),
        ),
        migrations.AlterField(
            model_name='solicitudmayorista',
            name='motivo_rechazo',
            field=models.TextField(blank=True, verbose_name='motivo del rechazo'),
        ),
        migrations.AlterField(
            model_name='solicitudmayorista',
            name='nit',
            field=models.CharField(help_text='Solo números; si tiene dígito de verificación, con guion.', max_length=20, verbose_name='NIT o cédula'),
        ),
        migrations.AlterField(
            model_name='solicitudmayorista',
            name='nombre_comercial',
            field=models.CharField(max_length=200, verbose_name='nombre comercial'),
        ),
        migrations.AlterField(
            model_name='solicitudmayorista',
            name='referido',
            field=models.CharField(blank=True, help_text='Persona o negocio que la recomendó, si aplica.', max_length=200, verbose_name='referido por'),
        ),
        migrations.AlterField(
            model_name='solicitudmayorista',
            name='representante_legal',
            field=models.CharField(max_length=200, verbose_name='representante legal'),
        ),
        migrations.AlterField(
            model_name='solicitudmayorista',
            name='revisado_en',
            field=models.DateTimeField(blank=True, null=True, verbose_name='revisado en'),
        ),
        migrations.AlterField(
            model_name='solicitudmayorista',
            name='revisado_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='solicitudes_revisadas', to=settings.AUTH_USER_MODEL, verbose_name='revisado por'),
        ),
        migrations.AlterField(
            model_name='solicitudmayorista',
            name='telefono',
            field=models.CharField(max_length=20, verbose_name='teléfono'),
        ),
        migrations.AlterField(
            model_name='solicitudmayorista',
            name='tipo_persona',
            field=models.CharField(choices=[('NATURAL', 'Persona natural'), ('EMPRESA', 'Empresa')], default='EMPRESA', max_length=10, verbose_name='tipo de persona'),
        ),
        migrations.AlterField(
            model_name='solicitudmayorista',
            name='usuario',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='solicitudes_mayorista', to=settings.AUTH_USER_MODEL, verbose_name='usuario'),
        ),
    ]