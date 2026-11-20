from django.apps import AppConfig


class MayoristasConfig(AppConfig):
    """Configuración de la app `mayoristas` (canal B2B).

    `default_auto_field` va declarado a propósito: sin él, el `id` de los
    modelos nuevos se crea como `AutoField` en cualquier Django anterior a
    6.1 y aparecería una migración espuria que cambiaría el `id` ya creado
    por `0001_initial` (que usa `BigAutoField`). Nunca se renumera una
    migración fusionada.

    VM-02 (JODS-96): la bandeja de solicitudes se enlaza desde el índice del
    admin de Django. Se hace aquí y no en `core` (DEC-04) porque es una
    pantalla más del módulo, con sus permisos, y así `core` no depende de
    `mayoristas`.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "mayoristas"

    def ready(self):
        """Añade el enlace a la bandeja en el índice del admin."""
        from django.contrib import admin

        admin.site.index_template = "mayoristas/admin_index.html"
