# Generated for JODS-194 — CFG-05: costos de envío.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [  # noqa: RUF012
        ("configuracion", "0005_alter_idioma_id_alter_impuesto_id_alter_moneda_id_and_more"),
    ]

    operations = [  # noqa: RUF012
        migrations.CreateModel(
            name="CostoEnvio",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "ciudad",
                    models.CharField(
                        help_text="Ciudad o municipio de destino.",
                        max_length=100,
                    ),
                ),
                (
                    "departamento",
                    models.CharField(
                        help_text="Departamento o región de destino.",
                        max_length=100,
                    ),
                ),
                (
                    "precio",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Costo del envío en pesos colombianos (COP).",
                        max_digits=10,
                    ),
                ),
                (
                    "tiempo_entrega",
                    models.CharField(
                        default="2 a 4 días hábiles",
                        help_text="Tiempo estimado informado al cliente.",
                        max_length=80,
                    ),
                ),
                ("activo", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Costo de envío",
                "verbose_name_plural": "Costos de envío",
                "ordering": ["departamento", "ciudad"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("ciudad", "departamento"),
                        name="uniq_costo_envio_ciudad_departamento",
                    ),
                ],
            },
        ),
    ]
