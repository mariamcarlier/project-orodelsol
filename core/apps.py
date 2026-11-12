"""Configuración de la aplicación `core` (catálogo y panel)."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Al arrancar, registra las señales de limpieza de archivos."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # Importar el módulo basta para conectar sus receptores (core/signals.py).
        from . import signals  # noqa: F401  pylint: disable=import-outside-toplevel,unused-import
