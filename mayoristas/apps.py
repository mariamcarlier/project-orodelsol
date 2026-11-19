from django.apps import AppConfig


class MayoristasConfig(AppConfig):
    """Configuración de la app `mayoristas` (canal B2B).

    `default_auto_field` va declarado a propósito: sin él, el `id` de los
    modelos nuevos se crea como `AutoField` en cualquier Django anterior a
    6.1 y aparecería una migración espuria que cambiaría el `id` ya creado
    por `0001_initial` (que usa `BigAutoField`). Nunca se renumera una
    migración fusionada.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "mayoristas"