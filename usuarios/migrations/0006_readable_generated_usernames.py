import re

from django.db import migrations
from django.utils.text import slugify


GENERATED_USERNAME = re.compile(r"^cliente_[0-9a-f]{32}$", re.IGNORECASE)


def replace_generated_usernames(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    database = schema_editor.connection.alias

    for usuario in Usuario.objects.using(database).order_by("pk").iterator():
        if not GENERATED_USERNAME.fullmatch(usuario.username):
            continue

        email_prefix = (usuario.email or "").partition("@")[0]
        base = slugify(usuario.first_name or email_prefix)[:150] or "cliente"
        username = base
        suffix = 2
        while Usuario.objects.using(database).filter(
            username__iexact=username
        ).exclude(pk=usuario.pk).exists():
            marker = f"-{suffix}"
            username = f"{base[:150 - len(marker)]}{marker}"
            suffix += 1

        usuario.username = username
        usuario.save(update_fields=["username"])


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0005_alter_usuario_documento_and_more"),
    ]

    operations = [
        migrations.RunPython(
            replace_generated_usernames,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
