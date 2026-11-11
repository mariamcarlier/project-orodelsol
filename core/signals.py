"""Limpieza de archivos cuando se elimina un registro del catálogo.

Django borra las filas, pero nunca los archivos. Estas señales cubren TODAS las
vías de borrado (vistas, panel, admin de Django, consola, borrados en bloque),
porque Django las emite por cada objeto eliminado.

El borrado en disco se programa con `transaction.on_commit`: si la operación se
revierte, los archivos siguen en su sitio.
"""

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from . import portadas, servicio_galeria
from .models import Coleccion, Producto


@receiver(post_delete, sender=Producto, dispatch_uid="core.limpiar_galeria_de_producto")
def limpiar_galeria_de_producto(instance, **kwargs):
    """Al eliminar un producto, vacía su carpeta `productos/<id>/`.

    Django entrega `sender`, `using` y los demás datos de la señal dentro de
    `kwargs`; aquí solo hace falta el objeto eliminado.
    """
    # El id se copia AHORA: Django lo borra del objeto al terminar la eliminación.
    producto_id = instance.pk
    if producto_id is None:
        return
    transaction.on_commit(
        lambda: servicio_galeria.borrar_carpeta_de_producto(producto_id)
    )


@receiver(post_delete, sender=Coleccion, dispatch_uid="core.limpiar_portada_de_coleccion")
def limpiar_portada_de_coleccion(sender, instance, **kwargs):
    """Al eliminar una colección, borra su archivo de portada.

    Solo si ninguna otra colección lo usa, y solo al confirmarse la transacción.
    Una colección con productos no llega aquí: Django se niega a eliminarla.
    """
    portadas.programar_borrado(sender, instance.imagen.name)
