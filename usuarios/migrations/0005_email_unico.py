from django.db import migrations, models
from django.db.models import Q
from django.db.models.functions import Lower


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0004_alter_usuario_foto_alter_usuario_telefono"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="email",
            field=models.EmailField(
                max_length=254,
                verbose_name="email address",
            ),
        ),
        migrations.AddConstraint(
            model_name="usuario",
            constraint=models.UniqueConstraint(
                Lower("email"),
                condition=~Q(email=""),
                name="unique_nonempty_email_ci",
            ),
        ),
    ]
