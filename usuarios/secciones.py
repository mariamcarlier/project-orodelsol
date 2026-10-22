"""Secciones de «Mi cuenta»: qué páginas existen y qué tarjetas muestra cada tipo de cuenta.

PUNTO ÚNICO DE DECISIÓN. Para agregar, quitar o reordenar una tarjeta o una
página de la cuenta se edita SOLO este archivo; la plantilla y las vistas leen
de aquí. Así no hay que repetir el mismo bloque de HTML por cada tarjeta.

Quién ve qué se decide con Usuario.rol_efectivo («ADMIN», «MAYORISTA» o
«CLIENTE»). Un superusuario cuenta como ADMIN aunque su campo «rol» diga otra
cosa (createsuperuser lo deja en CLIENTE).

Hoy ninguna de estas secciones tiene módulo propio (no existen los modelos de
direcciones, tallas, pedidos, etc.), así que sus páginas dicen «Disponible
próximamente». Cuando un módulo exista, esa clave pasa a tener su propia vista
y plantilla con datos reales, y su tarjeta deja de mostrar el estado vacío.
"""

ADMIN = "ADMIN"
MAYORISTA = "MAYORISTA"
CLIENTE = "CLIENTE"

# Páginas /usuario/cuenta/<slug>/ . «roles» dice quién puede abrirlas; el resto
# recibe 404 (no se revela que la página existe).
PAGINAS = {
    "tallas":          {"titulo": "Mis Tallas",             "roles": {CLIENTE}},
    "direcciones":     {"titulo": "Libreta de Direcciones", "roles": {CLIENTE, MAYORISTA}},
    "lista-de-deseos": {"titulo": "Mi Lista de Deseos",     "roles": {CLIENTE}},
    "pedido-reciente": {"titulo": "Mi Pedido Reciente",     "roles": {CLIENTE, MAYORISTA}},
    "empresa":         {"titulo": "Datos de mi Empresa",    "roles": {MAYORISTA}},
    "solicitud":       {"titulo": "Estado de mi Solicitud", "roles": {MAYORISTA}},
    "cotizaciones":    {"titulo": "Mis Cotizaciones",       "roles": {MAYORISTA}},
}

# Tarjetas de la página «Mi cuenta», EN EL ORDEN en que se ven (debajo de «Mi perfil»).
#   slug    -> página a la que lleva el enlace de la tarjeta (clave de PAGINAS)
#   titulo  -> título de la tarjeta
#   icono   -> nombre del dibujo en templates/usuarios/_icono_cuenta.html
#   enlace  -> texto del enlace de la tarjeta
#   ayuda   -> frase opcional antes del mensaje de estado vacío
#   vacio   -> mensaje cuando todavía no hay datos
#   roles   -> tipos de cuenta que ven la tarjeta
TARJETAS = (
    # ── Cliente ──
    {"slug": "tallas", "titulo": "Mis Tallas", "icono": "tallas", "enlace": "Ver tallas",
     "ayuda": "Guarda y consulta tus tallas de joyería aquí.",
     "vacio": "Aún no tienes tallas registradas.", "roles": {CLIENTE}},
    {"slug": "direcciones", "titulo": "Libreta de Direcciones", "icono": "direcciones", "enlace": "Añadir dirección",
     "vacio": "Aún no tienes direcciones guardadas.", "roles": {CLIENTE}},
    {"slug": "pedido-reciente", "titulo": "Mi Pedido más Reciente", "icono": "pedidos", "enlace": "Ver todo",
     "vacio": "Aún no hay pedidos disponibles.", "roles": {CLIENTE}},
    {"slug": "lista-de-deseos", "titulo": "Mi Lista de Deseos", "icono": "deseos", "enlace": "Ver todo",
     "vacio": "Aún no tienes productos en tu lista de deseos.", "roles": {CLIENTE}},
    # ── Mayorista ──
    {"slug": "empresa", "titulo": "Datos de mi Empresa", "icono": "empresa", "enlace": "Ver datos",
     "vacio": "Aún no has registrado los datos de tu empresa.", "roles": {MAYORISTA}},
    {"slug": "solicitud", "titulo": "Estado de mi Solicitud", "icono": "solicitud", "enlace": "Ver estado",
     "vacio": "Aún no hay una solicitud registrada.", "roles": {MAYORISTA}},
    {"slug": "cotizaciones", "titulo": "Mis Cotizaciones", "icono": "cotizaciones", "enlace": "Ver todo",
     "vacio": "Aún no tienes cotizaciones.", "roles": {MAYORISTA}},
    {"slug": "pedido-reciente", "titulo": "Mis Pedidos", "icono": "pedidos", "enlace": "Ver todo",
     "vacio": "Aún no hay pedidos disponibles.", "roles": {MAYORISTA}},
    {"slug": "direcciones", "titulo": "Libreta de Direcciones", "icono": "direcciones", "enlace": "Añadir dirección",
     "vacio": "Aún no tienes direcciones guardadas.", "roles": {MAYORISTA}},
)


def tarjetas_para(usuario):
    """Tarjetas que le corresponden a este usuario, en el orden de la página."""
    return [t for t in TARJETAS if usuario.rol_efectivo in t["roles"]]


def pagina_para(usuario, slug):
    """Datos de la página pedida, o None si no existe o no le corresponde a este usuario."""
    pagina = PAGINAS.get(slug)
    if pagina is None or usuario.rol_efectivo not in pagina["roles"]:
        return None
    return pagina
