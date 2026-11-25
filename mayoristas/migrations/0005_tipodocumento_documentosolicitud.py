"""Tipos de documento y documentos adjuntos (VM-19 · JODS-113).

Solo crea tablas: no siembra ningún tipo documental. Qué documentos se
piden es una decisión comercial pendiente (DEC-16) y el sistema no debe
aparentar que ya está definida.

`DocumentoSolicitud.archivo` guarda en el almacén PRIVADO (DEC-10): la ruta
queda fuera de MEDIA_URL y no hay forma de servirlo por URL directa.
"""

import django.db.models.deletion
import mayoristas.models
import mayoristas.storage
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mayoristas', '0004_dianohabil_tramoprecioreferencia'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TipoDocumento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=80, unique=True, verbose_name='nombre')),
                ('descripcion', models.TextField(blank=True, verbose_name='descripción')),
                ('obligatorio', models.BooleanField(default=False, help_text='Reservado para cuando comercial confirme qué documentos son imprescindibles. Hoy no se exige ninguno.', verbose_name='obligatorio')),
                ('activo', models.BooleanField(default=True, verbose_name='activo')),
            ],
            options={
                'verbose_name': 'tipo de documento',
                'verbose_name_plural': 'tipos de documento',
                'ordering': ('nombre',),
            },
        ),
        migrations.CreateModel(
            name='DocumentoSolicitud',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('archivo', models.FileField(max_length=255, storage=mayoristas.storage.AlmacenamientoPrivado(), upload_to=mayoristas.models.ruta_documento_mayorista, verbose_name='archivo')),
                ('nombre_original', models.CharField(blank=True, max_length=255, verbose_name='nombre original')),
                ('descripcion', models.CharField(blank=True, max_length=200, verbose_name='descripción')),
                ('subido_en', models.DateTimeField(auto_now_add=True, verbose_name='subido en')),
                ('solicitud', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documentos', to='mayoristas.solicitudmayorista', verbose_name='solicitud')),
                ('subido_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='documentos_subidos', to=settings.AUTH_USER_MODEL, verbose_name='subido por')),
                ('tipo', models.ForeignKey(blank=True, help_text='Opcional mientras no haya tipos configurados (DEC-16).', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='documentos', to='mayoristas.tipodocumento', verbose_name='tipo de documento')),
            ],
            options={
                'verbose_name': 'documento de solicitud',
                'verbose_name_plural': 'documentos de solicitud',
                'ordering': ('-subido_en',),
            },
        ),
    ]
