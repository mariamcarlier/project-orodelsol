"""Selectores del canal B2B: SOLO lectura.

Un selector no escribe, no valida ni lanza reglas de negocio: devuelve datos
ya preparados para una vista. Así las consultas quedan en un único sitio y la
vista no arma querysets a mano.
"""

from django.db.models import Count, Q

from .models import SolicitudMayorista


def solicitud_activa_de(usuario):
    """Solicitud PENDIENTE o APROBADA del usuario, o None si no tiene.

    Es la consulta que decide si alguien puede volver a solicitar. Solo tiene
    sentido con un usuario autenticado.
    """
    if not getattr(usuario, "is_authenticated", False):
        return None
    return (
        SolicitudMayorista.objects.activas()
        .filter(usuario=usuario)
        .order_by("-creado_en")
        .first()
    )


def ultima_solicitud_de(usuario):
    """La solicitud más reciente del usuario, sea cual sea su estado.

    Es la que se muestra en «Estado de mi solicitud»: si la última fue
    rechazada, hay que poder enseñar el motivo y el enlace para volver a
    solicitar.
    """
    if not getattr(usuario, "is_authenticated", False):
        return None
    return (
        SolicitudMayorista.objects.filter(usuario=usuario)
        .order_by("-creado_en")
        .first()
    )


def puede_solicitar(usuario, solicitud=None):
    """Datos de decisión para la vista de solicitud, sin lógica duplicada.

    Devuelve un diccionario con:
      - ``puede``: si el formulario debe mostrarse.
      - ``motivo``: por qué no, con el texto que se enseña en pantalla.
      - ``solicitud``: la solicitud activa que bloquea, si la hay.

    Nota: **no** decide por rol. Que el rol sea o no CLIENTE se comprueba en la
    vista con `Usuario.rol_efectivo`, porque es una regla de acceso y no de
    datos.
    """
    activa = solicitud if solicitud is not None else solicitud_activa_de(usuario)
    if activa is None:
        return {"puede": True, "motivo": "", "solicitud": None}
    if activa.estado == SolicitudMayorista.Estado.PENDIENTE:
        motivo = "Tu solicitud está en revisión."
    else:
        motivo = "Tu acceso mayorista ya está aprobado."
    return {"puede": False, "motivo": motivo, "solicitud": activa}


# ═══════════════════════════════════════════════════════════════════════
# VM-02 (JODS-96) · Bandeja de verificación
# ═══════════════════════════════════════════════════════════════════════

ESTADOS_FILTRO = (
    SolicitudMayorista.Estado.PENDIENTE,
    SolicitudMayorista.Estado.APROBADA,
    SolicitudMayorista.Estado.RECHAZADA,
)


def bandeja_solicitudes(estado=None, busqueda=""):
    """Solicitudes para la bandeja de verificación, ya ordenadas.

    Args:
        estado: uno de los códigos de `ESTADOS_FILTRO`; cualquier otro valor o
            vacío devuelve todas.
        busqueda: texto libre que se compara con nombre comercial, NIT,
            ciudad y correo del solicitante. Los filtros se combinan con AND.

    Returns:
        QuerySet con `select_related("usuario")` y `revisado_por` precargados,
        para que la tabla no dispare una consulta por fila.
    """
    consulta = SolicitudMayorista.objects.select_related("usuario", "revisado_por")

    if estado in ESTADOS_FILTRO:
        consulta = consulta.filter(estado=estado)

    texto = (busqueda or "").strip()
    if texto:
        consulta = consulta.filter(
            Q(nombre_comercial__icontains=texto)
            | Q(nit__icontains=texto)
            | Q(ciudad__icontains=texto)
            | Q(correo__icontains=texto)
            | Q(usuario__email__icontains=texto)
        )

    return consulta


def resumen_bandeja():
    """Cuántas solicitudes hay en cada estado, para las pestañas de la bandeja.

    Un solo agregado en lugar de tres `count()`: la bandeja enseña siempre los
    tres números aunque esté filtrando por uno.
    """
    conteo = dict(
        SolicitudMayorista.objects.values_list("estado")
        .annotate(total=Count("pk"))
        .values_list("estado", "total")
    )
    resumen = {clave: conteo.get(clave, 0) for clave in ESTADOS_FILTRO}
    resumen["TODAS"] = sum(resumen.values())
    return resumen


def solicitud_para_revision(pk):
    """Una solicitud concreta con lo necesario para revisarla, o None.

    Devuelve None en lugar de lanzar `DoesNotExist`: la vista decide si eso es
    un 404. Se precargan usuario y revisor para no repetir consultas.
    """
    return (
        SolicitudMayorista.objects.select_related("usuario", "revisado_por")
        .filter(pk=pk)
        .first()
    )


# ═══════════════════════════════════════════════════════════════════════
# VM-16 (JODS-110) · Tramos de precio de referencia
# ═══════════════════════════════════════════════════════════════════════


def tramos_de_referencia():
    """Tramos activos, ordenados por cantidad mínima.

    Incluye los que NO tienen porcentaje: la pantalla debe poder distinguir
    «tramo definido pero sin cifra» de «tramo inexistente».
    """
    from .models import TramoPrecioReferencia

    return TramoPrecioReferencia.objects.filter(activo=True).order_by(
        "cantidad_minima"
    )


def tramos_configurados():
    """Solo los tramos ACTIVOS y CON porcentaje: los únicos aplicables.

    Es el selector que consulta el catálogo antes de decidir si puede mostrar
    un precio con descuento. Si devuelve vacío, no se calcula nada (DEC-18).
    """
    from .models import TramoPrecioReferencia

    return TramoPrecioReferencia.objects.filter(
        activo=True, porcentaje__isnull=False
    ).order_by("cantidad_minima")


def hay_tramos_configurados():
    """True si existe al menos un tramo aplicable.

    Se usa en las plantillas para decidir entre enseñar los porcentajes o el
    aviso «Tramos pendientes de configuración» (DEC-18).
    """
    return tramos_configurados().exists()


def tramo_para_cantidad(cantidad):
    """Tramo aplicable a una cantidad, o None.

    Devuelve None en dos casos distintos, y la vista debe tratarlos igual:
    - no hay ningún tramo configurado (DEC-18), o
    - la cantidad no cae en ningún rango definido.

    No calcula precios: solo elige el tramo. El cálculo vive en el servicio.
    """
    if not cantidad or cantidad < 1:
        return None
    for tramo in tramos_configurados():
        if tramo.cantidad_maxima is None:
            if cantidad >= tramo.cantidad_minima:
                return tramo
        elif tramo.cantidad_minima <= cantidad <= tramo.cantidad_maxima:
            return tramo
    return None


# ═══════════════════════════════════════════════════════════════════════
# VM-03 (JODS-97) · Catálogo mayorista
# ═══════════════════════════════════════════════════════════════════════
#
# DEC-01: disponible ≡ al menos UNA variante ACTIVA con stock > 0. Los
# productos sin disponibilidad se EXCLUYEN del catálogo B2B. No se dice
# «en fabricación» ni se promete nada que no esté en stock.
#
# Q-01 (precio): `VarianteProducto.precio_final` es una @property
# (`producto.precio + precio_adicional`), así que NO se puede agregar en SQL.
# Se reproduce la misma suma con `Min("producto__precio") + Min(
# "precio_adicional")` sobre las variantes disponibles. Es la misma fórmula,
# escrita de forma que la base de datos pueda calcularla; no se añade ningún
# recargo ni se altera el cálculo comercial.
#
# `core` NO se modifica: este selector solo lee.

def _variantes_disponibles():
    """Variantes que cuentan para «disponible»: activas y con stock."""
    from core.models import VarianteProducto

    return VarianteProducto.objects.filter(activa=True, stock__gt=0)


def catalogo_mayorista(busqueda=""):
    """Productos con al menos una variante disponible, con su precio «Desde».

    Args:
        busqueda: texto libre sobre nombre, detalle o colección.

    Returns:
        QuerySet de `core.Producto` visibles públicamente, con al menos una
        variante disponible, anotado con:
          - ``variantes_disponibles``: cuántas variantes activas con stock hay.
          - ``precio_desde``: el menor `precio_final` entre ellas (Decimal).

        Se ordena por `precio_desde` ascendente y luego por nombre, para que
        el catálogo sea estable entre cargas.
    """
    from django.db.models import Count, F, Min, Q

    from core.models import Producto

    productos = (
        Producto.objects.publicos()
        .filter(variantes__activa=True, variantes__stock__gt=0)
        .annotate(
            variantes_disponibles=Count(
                "variantes",
                filter=Q(variantes__activa=True, variantes__stock__gt=0),
                distinct=True,
            ),
            precio_desde=Min(
                F("precio") + F("variantes__precio_adicional"),
                filter=Q(variantes__activa=True, variantes__stock__gt=0),
            ),
        )
        .select_related("coleccion")
        .distinct()
    )

    texto = (busqueda or "").strip()
    if texto:
        productos = productos.filter(
            Q(nombre__icontains=texto)
            | Q(detalle__icontains=texto)
            | Q(coleccion__nombre__icontains=texto)
        )

    return productos.order_by("precio_desde", "nombre")


def producto_mayorista(pk):
    """Producto del catálogo B2B por id, o None si no es visible/disponible.

    Se usa en la ficha y al cotizar: un producto que dejó de estar disponible
    no debe poder pedirse. Devolver None (y no lanzar) deja la decisión a la
    vista, igual que en el resto del módulo.
    """
    if not pk:
        return None
    return catalogo_mayorista().filter(pk=pk).first()


def variantes_disponibles_de(producto):
    """Variantes activas con stock de un producto, ordenadas por precio final.

    Es la lista que se ofrece al cotizar. La ordenación se hace en Python
    porque `precio_final` es una propiedad, y el número de variantes por
    producto es pequeño.
    """
    return sorted(
        _variantes_disponibles()
        .filter(producto=producto)
        .select_related("producto", "talla", "material"),
        key=lambda variante: (variante.precio_final, variante.sku),
    )
