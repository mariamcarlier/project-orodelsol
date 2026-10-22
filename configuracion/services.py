"""Servicios de configuración para Joyería Oro del Sol.

Puntos de integración desacoplados para los módulos de la tienda.
"""

from .models import PlantillaDocumento


def obtener_plantilla_vigente(tipo_documento, pedido=None, producto=None):
    """Servicio de asociación automática de plantillas documentales (CFG-07).

    Dado un tipo de documento ('CERTIFICADO', 'GARANTIA', 'FACTURA', 'OTRO') y
    opcionalmente el contexto de un pedido o producto, resuelve y devuelve
    la plantilla documental vigente que debe aplicarse.

    Punto de integración pendiente:
    Cuando el modelo de Pedido/Checkout sea implementado en sprints futuros,
    este servicio se conectará al generador de PDFs y a la emisión de comprobantes.
    """
    return PlantillaDocumento.obtener_vigente(tipo_documento)
