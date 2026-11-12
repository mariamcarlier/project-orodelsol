"""Gestión CRUD de los modelos del proyecto desde una sola pantalla."""

from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.forms import inlineformset_factory
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode

from configuracion.forms import (
    CostoEnvioForm,
    IdiomaForm,
    ImpuestoForm,
    MetodoPagoForm,
    MonedaForm,
    ParametroGeneralForm,
    PlantillaDocumentoForm,
    PoliticaComercialForm,
)
from configuracion.models import (
    CostoEnvio,
    Idioma,
    Impuesto,
    MetodoPago,
    Moneda,
    ParametroGeneral,
    PlantillaDocumento,
    PoliticaComercial,
)
from usuarios.forms import AdministrarUsuarioForm, RegistroUsuarioForm
from usuarios.models import Usuario

from . import servicio_galeria
from .models import Coleccion, Material, Producto, Talla, VarianteProducto
from .portadas import CampoPortada
from .vistas_galeria import contexto_galeria


class GrupoPermisosForm(forms.ModelForm):
    ETIQUETAS_ACCION = {
        "add": "Agregar",
        "change": "Cambiar",
        "delete": "Eliminar",
        "view": "Ver",
    }

    class Meta:
        model = Group
        fields = ("name", "permissions")
        labels = {
            "name": "Nombre del grupo",
            "permissions": "Permisos del grupo",
        }
        help_texts = {
            "permissions": (
                "Los usuarios miembros del grupo reciben estos permisos."
            ),
        }
        widgets = {
            "permissions": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["permissions"].label_from_instance = self.etiqueta_permiso

    @classmethod
    def etiqueta_permiso(cls, permiso):
        accion = permiso.codename.split("_", maxsplit=1)[0]
        etiqueta_accion = cls.ETIQUETAS_ACCION.get(accion, permiso.name)
        return f"{permiso.content_type.app_labeled_name} · {etiqueta_accion}"


class AdministrarUsuarioCreacionForm(RegistroUsuarioForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label="Grupos y permisos",
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta(RegistroUsuarioForm.Meta):
        fields = (*RegistroUsuarioForm.Meta.fields, "groups")


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = (
            "codigo",
            "nombre",
            "coleccion",
            "detalle",
            "descripcion",
            "precio",
            "imagen_url",
            "destacado",
            "activo",
            "es_borrador",
            "tallas",
            "materiales",
        )
        labels = {
            "codigo": "Código",
            "nombre": "Nombre",
            "coleccion": "Colección",
            "detalle": "Detalle",
            "descripcion": "Descripción",
            "precio": "Precio",
            "imagen_url": "URL de la imagen",
            "destacado": "Destacado",
            "activo": "Activo",
            "es_borrador": "Borrador",
            "tallas": "Tallas permitidas",
            "materiales": "Materiales permitidos",
        }
        help_texts = {
            "codigo": "Déjalo vacío para generarlo automáticamente. Una vez creado no se puede cambiar.",
            "es_borrador": "Un borrador no se muestra en la tienda aunque esté activo.",
            "imagen_url": (
                "Solo se usa mientras el producto no tenga fotografías en su galería."
            ),
        }
        widgets = {
            "codigo": forms.TextInput(attrs={"class": "form-control"}),
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "coleccion": forms.Select(attrs={"class": "form-select select2"}),
            "detalle": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "precio": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "imagen_url": forms.URLInput(attrs={"class": "form-control"}),
            "destacado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "es_borrador": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "tallas": forms.CheckboxSelectMultiple,
            "materiales": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.codigo:
            self.fields["codigo"].disabled = True
        if self.instance.pk and self.instance.galeria_gestionada:
            # La galería ya es la fuente de las imágenes (Paso 03d): la URL
            # antigua no se muestra ni se puede cambiar, pero su valor se conserva.
            del self.fields["imagen_url"]
        # PROD-12: nombre y precio solo son obligatorios al publicar.
        # En borrador (o inactivo) se permite guardar incompleto; la
        # validación de publicación vive en clean() y en Producto.clean().
        self.fields["nombre"].required = False
        self.fields["precio"].required = False
        self.fields["nombre"].help_text = (
            "Obligatorio al publicar. En borrador puede quedar vacío."
        )
        self.fields["precio"].help_text = (
            "Obligatorio y mayor a cero al publicar. En borrador puede quedar en 0."
        )

    def clean(self):
        cleaned = super().clean()
        # Los checkboxes pueden faltar en cleaned_data si hubo un error
        # previo; en ese caso se lee el dato crudo enviado.
        def _marcado(nombre):
            if nombre in cleaned:
                return bool(cleaned[nombre])
            return self.data.get(self.add_prefix(nombre)) in (
                "on", "true", "True", "1",
            )

        es_borrador = _marcado("es_borrador")
        nombre = (cleaned.get("nombre") or "").strip()
        precio = cleaned.get("precio")

        if es_borrador:
            # Borrador o inactivo: guardar incompleto, dejando valores
            # que la BD acepta (precio NOT NULL, nombre cadena).
            cleaned["nombre"] = nombre
            if precio is None:
                cleaned["precio"] = Decimal("0")
            return cleaned

        errores = {}
        if not nombre:
            errores["nombre"] = "El nombre es obligatorio para publicar."
        if precio is None or precio <= 0:
            errores["precio"] = "El precio debe ser mayor a cero para publicar."
        if errores:
            raise forms.ValidationError(errores)
        return cleaned


class VarianteForm(forms.ModelForm):
    class Meta:
        model = VarianteProducto
        fields = ("talla", "material", "sku", "peso_gramos", "precio_adicional", "stock", "activa")
        widgets = {
            "talla": forms.Select(attrs={"class": "form-select"}),
            "material": forms.Select(attrs={"class": "form-select"}),
            "sku": forms.TextInput(attrs={"class": "form-control"}),
            "peso_gramos": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "precio_adicional": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "stock": forms.NumberInput(attrs={"class": "form-control"}),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


VarianteFormSet = inlineformset_factory(
    Producto,
    VarianteProducto,
    form=VarianteForm,
    extra=1,
    can_delete=True
)


MENSAJE_ARCHIVO_CON_DIRECCION = (
    "Una colección usa un archivo o una dirección (URL), nunca los dos. "
    "Borra la dirección y vuelve a elegir la fotografía, o guarda sin subir archivo."
)
MENSAJE_DIRECCION_CON_ARCHIVO = (
    "Esta colección ya tiene una portada subida como archivo. "
    "Marca «Quitar la portada actual» para usar una dirección, o deja este campo vacío."
)


class ColeccionForm(forms.ModelForm):
    """Colección con su portada: un archivo propio O una dirección, nunca los dos.

    El archivo se valida y se optimiza en `CampoPortada` (`core/portadas.py`);
    este formulario solo decide qué pasa cuando llegan las dos fuentes.
    """

    imagen = CampoPortada()

    class Meta:
        model = Coleccion
        fields = ("nombre", "descripcion", "temporada", "imagen_url", "imagen", "activa")
        labels = {
            "nombre": "Nombre",
            "descripcion": "Descripción",
            "temporada": "Temporada",
            "imagen_url": "URL de imagen",
            "activa": "Activa",
        }
        help_texts = {
            "imagen_url": (
                "Dirección de una imagen ya publicada en internet. "
                "Déjala vacía si subes un archivo."
            ),
        }
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "temporada": forms.TextInput(attrs={"class": "form-control"}),
            "imagen_url": forms.URLInput(attrs={"class": "form-control"}),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        datos = super().clean()
        if "imagen" not in datos or "imagen_url" not in datos:
            return datos  # alguno de los dos campos ya tiene su propio error
        # `imagen` trae la portada que quedaría: la nueva, la que ya había, o nada
        # (None si no hay; False si se pidió quitarla).
        if datos["imagen"] and datos["imagen_url"]:
            if "imagen" in self.changed_data:
                self.add_error("imagen", MENSAJE_ARCHIVO_CON_DIRECCION)
            else:
                self.add_error("imagen_url", MENSAJE_DIRECCION_CON_ARCHIVO)
        return datos


GRUPOS_MENU = {
    "configuracion": {"title": "Configuración", "icon": "bx-cog"},
}

RECURSOS = (
    {
        "key": "costos_envio",
        "title": "Costos de envío",
        "description": "Configura tarifas y tiempos de entrega por ciudad y departamento.",
        "icon": "bxs-truck",
        "grupo": "configuracion",
        "grupo_orden": "5",
        "model": CostoEnvio,
        "create_form": CostoEnvioForm,
        "edit_form": CostoEnvioForm,
        "columns": (
            ("Ciudad", "ciudad"),
            ("Departamento", "departamento"),
            ("Costo (COP)", "precio"),
            ("Tiempo estimado", "tiempo_entrega"),
            ("Activo", "activo"),
        ),
        "search_fields": ("ciudad__icontains", "departamento__icontains"),
        "bulk_field": "activo",
    },
    {
        "key": "metodos_pago",
        "title": "Medios de pago",
        "description": "Administra las formas de pago disponibles para las compras.",
        "icon": "bx-credit-card",
        "grupo": "configuracion",
        "grupo_orden": "6",
        "model": MetodoPago,
        "create_form": MetodoPagoForm,
        "edit_form": MetodoPagoForm,
        "columns": (
            ("Nombre", "nombre"),
            ("Tipo", "tipo_display"),
            ("Banco / Entidad", "banco"),
            ("Cuenta / Celular", "numero_cuenta"),
            ("Titular", "titular"),
            ("Activo", "activo"),
        ),
        "search_fields": (
            "nombre__icontains",
            "banco__icontains",
            "titular__icontains",
            "numero_cuenta__icontains",
        ),
        "bulk_field": "activo",
    },
    {
        "key": "productos",
        "title": "Productos",
        "description": "Crea y actualiza el catálogo de joyas y su disponibilidad.",
        "icon": "bx-package",
        "model": Producto,
        "create_form": ProductoForm,
        "edit_form": ProductoForm,
        "columns": (
            ("Código", "codigo"),
            ("Nombre", "nombre"),
            ("Colección", "coleccion__nombre"),
            ("Precio", "precio"),
            ("Borrador", "es_borrador"),
            ("Activo", "activo"),
        ),
        "search_fields": ("codigo__icontains", "nombre__icontains", "detalle__icontains"),
        "bulk_field": "activo",
    },
    {
        "key": "colecciones",
        "title": "Colecciones",
        "description": "Organiza productos en colecciones y temporadas.",
        "icon": "bx-collection",
        "model": Coleccion,
        "create_form": ColeccionForm,
        "edit_form": ColeccionForm,
        "columns": (
            ("Nombre", "nombre"),
            ("Temporada", "temporada"),
            ("Activa", "activa"),
        ),
        "search_fields": ("nombre__icontains", "descripcion__icontains"),
        "bulk_field": "activa",
    },
    {
        "key": "usuarios",
        "title": "Usuarios",
        "description": "Consulta cuentas, perfiles, roles y estado de acceso.",
        "icon": "bx-user",
        "model": Usuario,
        "create_form": AdministrarUsuarioCreacionForm,
        "edit_form": AdministrarUsuarioForm,
        "columns": (
            ("Usuario", "username"),
            ("Nombre", "first_name"),
            ("Correo", "email"),
            ("Rol", "rol"),
            ("Personal", "is_staff"),
            ("Activo", "is_active"),
        ),
        "search_fields": (
            "username__icontains",
            "email__icontains",
            "first_name__icontains",
            "last_name__icontains",
            "documento__icontains",
        ),
        "bulk_field": "is_active",
    },
    {
        "key": "grupos",
        "title": "Grupos y permisos",
        "description": "Agrupa usuarios y asigna permisos por modelo.",
        "icon": "bx-group",
        "model": Group,
        "create_form": GrupoPermisosForm,
        "edit_form": GrupoPermisosForm,
        "columns": (
            ("Nombre del grupo", "name"),
            ("Permisos asignados", "permissions__count"),
        ),
        "search_fields": ("name__icontains",),
    },
    {
        "key": "impuestos",
        "title": "Impuestos",
        "description": "Configura tasas y vigencia de impuestos aplicables.",
        "icon": "bx-receipt",
        "grupo": "configuracion",
        "grupo_orden": "2",
        "model": Impuesto,
        "create_form": ImpuestoForm,
        "edit_form": ImpuestoForm,
        "columns": (
            ("Nombre", "nombre"),
            ("Tasa (%)", "tasa"),
            ("Vigente", "vigente"),
        ),
        "search_fields": ("nombre__icontains",),
        "bulk_field": "vigente",
    },
    {
        "key": "monedas",
        "title": "Monedas",
        "description": "Administra monedas, tasas de cambio y moneda principal.",
        "icon": "bx-dollar-circle",
        "grupo": "configuracion",
        "grupo_orden": "3",
        "model": Moneda,
        "create_form": MonedaForm,
        "edit_form": MonedaForm,
        "columns": (
            ("Código", "codigo_iso"),
            ("Nombre", "nombre"),
            ("Tasa", "tasa_cambio"),
            ("Principal", "es_principal"),
            ("Activa", "activa"),
        ),
        "search_fields": ("codigo_iso__icontains", "nombre__icontains"),
        "bulk_field": "activa",
    },
    {
        "key": "idiomas",
        "title": "Idiomas",
        "description": "Configura los idiomas disponibles y el idioma principal.",
        "icon": "bx-globe",
        "grupo": "configuracion",
        "grupo_orden": "4",
        "model": Idioma,
        "create_form": IdiomaForm,
        "edit_form": IdiomaForm,
        "columns": (
            ("Código", "codigo"),
            ("Nombre", "nombre"),
            ("Principal", "es_principal"),
            ("Activo", "activo"),
        ),
        "search_fields": ("codigo__icontains", "nombre__icontains"),
        "bulk_field": "activo",
    },
    {
        "key": "parametros",
        "title": "Parámetros generales",
        "description": "Edita los datos de contacto y la información general de la tienda.",
        "icon": "bx-cog",
        "grupo": "configuracion",
        "grupo_orden": "1",
        "model": ParametroGeneral,
        "create_form": ParametroGeneralForm,
        "edit_form": ParametroGeneralForm,
        "columns": (
            ("Tienda", "nombre_tienda"),
            ("NIT", "nit"),
            ("Correo", "correo_contacto"),
            ("Teléfono", "telefono_contacto"),
        ),
        "search_fields": ("nombre_tienda__icontains", "nit__icontains"),
        "deletable": False,
        "singleton": True,
    },
    {
        "key": "politicas_comerciales",
        "title": "Políticas comerciales",
        "description": "Define mínimos de compra, envío gratis y reglas comerciales.",
        "icon": "bx-badge-check",
        "grupo": "configuracion",
        "grupo_orden": "7",
        "model": PoliticaComercial,
        "create_form": PoliticaComercialForm,
        "edit_form": PoliticaComercialForm,
        "columns": (
            ("Mínimo B2C (COP)", "monto_minimo_compra_b2c"),
            ("Mínimo B2B (COP)", "monto_minimo_compra_b2b"),
            ("Envío gratis desde", "monto_minimo_envio_gratis"),
            ("Reserva carrito", "tiempo_reserva_display"),
            ("Vigencia cupones", "vigencia_cupones_display"),
        ),
        "search_fields": (),
        "deletable": False,
        "singleton": True,
    },
    {
        "key": "plantillas_documentos",
        "title": "Certificados y documentos",
        "description": "Administra certificados y documentos disponibles para la tienda.",
        "icon": "bxs-file-pdf",
        "grupo": "configuracion",
        "grupo_orden": "8",
        "model": PlantillaDocumento,
        "create_form": PlantillaDocumentoForm,
        "edit_form": PlantillaDocumentoForm,
        "columns": (
            ("Nombre", "nombre"),
            ("Tipo", "tipo_display"),
            ("Versión", "version_display"),
            ("Archivo", "archivo_enlace"),
            ("Vigente", "activa"),
            ("Subido por", "subido_por__username"),
            ("Fecha creación", "creado_en_display"),
        ),
        "search_fields": ("nombre__icontains", "tipo__icontains"),
        "bulk_field": "activa",
    },
)


def permiso(modelo, accion):
    return f"{modelo._meta.app_label}.{accion}_{modelo._meta.model_name}"


def recursos_visibles(usuario):
    return [
        item
        for item in RECURSOS
        if usuario.has_perm(permiso(item["model"], "view"))
    ]


def construir_menu(recursos, clave_activa=None):
    sueltos = []
    agrupados = {}
    for recurso in recursos:
        entrada = {"recurso": recurso, "activo": recurso["key"] == clave_activa}
        clave_grupo = recurso.get("grupo")
        if clave_grupo in GRUPOS_MENU:
            agrupados.setdefault(clave_grupo, []).append(entrada)
        else:
            sueltos.append(entrada)

    grupos = []
    for clave_grupo, datos in GRUPOS_MENU.items():
        items = sorted(
            agrupados.get(clave_grupo, []),
            key=lambda entrada: entrada["recurso"].get("grupo_orden", 0),
        )
        if items:
            grupos.append(
                {
                    "key": clave_grupo,
                    "title": datos["title"],
                    "icon": datos["icon"],
                    "items": items,
                    "abierto": any(entrada["activo"] for entrada in items),
                }
            )
    return {"sueltos": sueltos, "grupos": grupos}

def construir_migas(clave=None):
    """Arma las migas de pan: Panel > [grupo] > [recurso].

    Cada miga es {"title": str, "url": str | None}. La última nunca lleva
    enlace porque es la página actual; el grupo tampoco, porque no tiene
    página propia.
    """
    migas = [{"title": "Panel", "url": reverse("core:admin_dashboard")}]
    if clave is None:
        migas[0]["url"] = None
        return migas

    recurso = next((r for r in RECURSOS if r["key"] == clave), None)
    if recurso is None:
        return migas
    grupo = GRUPOS_MENU.get(recurso.get("grupo"))
    if grupo:
        migas.append({"title": grupo["title"], "url": None})
    migas.append({"title": recurso["title"], "url": None})
    return migas


def obtener_celda(objeto, campo):
    valor = objeto
    for parte in campo.split("__"):
        valor = getattr(valor, parte, None)
        if valor is None:
            return "—"
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    return valor or "—"


def preparar_formulario(formulario, usuario):
    puede_asignar_grupos = usuario.has_perm("auth.view_group") and usuario.has_perm(
        "auth.change_group"
    )
    if "groups" in formulario.fields and not puede_asignar_grupos:
        formulario.fields.pop("groups")

    for campo in formulario.fields.values():
        if isinstance(campo.widget, forms.CheckboxSelectMultiple):
            campo.widget.attrs.setdefault("class", "dashboard-permissions")
        else:
            clase = (
                "dashboard-checkbox"
                if getattr(campo.widget, "input_type", None) == "checkbox"
                else "dashboard-input"
            )
            campo.widget.attrs.setdefault("class", clase)
    return formulario


# Al volver de una acción de la galería, la dirección lleva `?galeria=<id>`:
# con eso el panel reabre la ficha de ese producto con sus fotografías a la vista.
PARAMETRO_GALERIA = "galeria"


def direccion_de_galeria(request, producto):
    """Dirección de esta misma página del panel con la ficha del producto abierta."""
    parametros = {}
    for nombre in ("q", "page"):
        valor = request.GET.get(nombre, "").strip()
        if valor:
            parametros[nombre] = valor
    parametros[PARAMETRO_GALERIA] = producto.pk
    return f"{request.path}?{urlencode(parametros)}#registros"


def adjuntar_galerias(request, filas):
    """Añade a cada fila de producto los datos de su bloque de fotografías.

    Las galerías de toda la página se leen con una sola consulta.
    """
    galerias = servicio_galeria.listar_por_producto([fila["objeto"] for fila in filas])
    abierta = request.GET.get(PARAMETRO_GALERIA)
    for fila in filas:
        producto = fila["objeto"]
        fila["galeria"] = contexto_galeria(
            producto,
            galerias[producto.pk],
            siguiente=direccion_de_galeria(request, producto),
        )
        fila["abrir_galeria"] = abierta == str(producto.pk)


def crear_contexto(request, clave, formularios=None, formulario_abierto=None):
    formularios = formularios or {}
    menu = recursos_visibles(request.user)
    configuracion = next((item for item in RECURSOS if item["key"] == clave), None)
    if configuracion is None:
        raise PermissionDenied("El módulo solicitado no está disponible.")

    modelo = configuracion["model"]
    if not request.user.has_perm(permiso(modelo, "view")):
        raise PermissionDenied

    query = request.GET.get("q", "").strip()
    registros = modelo.objects.all().order_by("pk")
    if modelo is Group:
        registros = registros.prefetch_related("permissions")
    if configuracion.get("singleton"):
        registros = registros.filter(pk=1)
    if query:
        filtro = Q()
        for campo in configuracion["search_fields"]:
            filtro |= Q(**{campo: query})
        registros = registros.filter(filtro)

    paginador = Paginator(registros, 25)
    pagina = paginador.get_page(request.GET.get("page"))
    puede_cambiar = request.user.has_perm(permiso(modelo, "change"))
    filas = []
    for objeto in pagina.object_list:
        fila = {
            "objeto": objeto,
            "celdas": [
                str(objeto.permissions.count())
                if campo == "permissions__count"
                else obtener_celda(objeto, campo)
                for _, campo in configuracion["columns"]
            ],
            "formulario": preparar_formulario(
                formularios.get(
                    (clave, "edit", str(objeto.pk)),
                    configuracion["edit_form"](
                        instance=objeto,
                        prefix=f"{clave}-{objeto.pk}",
                    )
                    if configuracion["edit_form"] and puede_cambiar
                    else None,
                ),
                request.user,
            )
            if configuracion["edit_form"] and puede_cambiar
            else None,
            "formulario_contrasena": formularios.get(
                (clave, "password", str(objeto.pk))
            ),
            "abrir_edicion": formulario_abierto
            == (clave, "edit", str(objeto.pk)),
            "abrir_contrasena": formulario_abierto
            == (clave, "edit", str(objeto.pk))
            and (clave, "password", str(objeto.pk)) in formularios,
        }
        if modelo is Usuario and puede_cambiar:
            fila["formulario_contrasena"] = preparar_formulario(
                fila["formulario_contrasena"]
                or SetPasswordForm(objeto, prefix=f"contrasena-{objeto.pk}"),
                request.user,
            )
        filas.append(fila)

    puede_crear = bool(configuracion["create_form"]) and request.user.has_perm(
        permiso(modelo, "add")
    )
    if configuracion.get("singleton") and pagina.paginator.count:
        puede_crear = False
    crear_formulario = None
    if puede_crear:
        crear_formulario = preparar_formulario(
            formularios.get(
                (clave, "create", ""),
                configuracion["create_form"](prefix=f"{clave}-nuevo"),
            ),
            request.user,
        )

    recurso = {
        **configuracion,
        "filas": filas,
        "columnas": [nombre for nombre, _ in configuracion["columns"]],
        "pagina": pagina,
        "busqueda": query,
        "crear_formulario": crear_formulario,
        "puede_cambiar": puede_cambiar,
        "puede_borrar": configuracion.get("deletable", True)
        and request.user.has_perm(permiso(modelo, "delete")),
        "bulk_field": configuracion.get("bulk_field") if puede_cambiar else None,
        "abrir_crear": formulario_abierto == (clave, "create", ""),
    }
    
    if modelo is Producto and puede_cambiar:
        for fila in filas:
            formset_key = (clave, "formset", str(fila["objeto"].pk))
            if formset_key in formularios:
                fila["variante_formset"] = formularios[formset_key]
            else:
                fila["variante_formset"] = VarianteFormSet(
                    instance=fila["objeto"], 
                    prefix=f"variantes-{fila['objeto'].pk}"
                )
        adjuntar_galerias(request, filas)

    return {
        "recursos": menu, 
        "recurso": recurso,
        "menu_lateral": construir_menu(menu, clave),
        "migas": construir_migas(clave),
    }


def procesar_accion(request, clave, configuracion):
    formularios = {}
    formulario_abierto = None

    if request.POST.get("recurso") != clave:
        raise PermissionDenied("El formulario corresponde a otro módulo.")

    accion = request.POST.get("accion")
    modelo = configuracion["model"]
    if accion == "create":
        if not configuracion["create_form"]:
            raise PermissionDenied("No se permite crear este tipo de registro.")
        if not request.user.has_perm(permiso(modelo, "add")):
            raise PermissionDenied
        objeto = None
        clase_formulario = configuracion["create_form"]
    elif accion == "edit":
        if not configuracion["edit_form"]:
            raise PermissionDenied("No se permite editar este tipo de registro.")
        if not request.user.has_perm(permiso(modelo, "change")):
            raise PermissionDenied
        objeto = get_object_or_404(modelo, pk=request.POST.get("registro"))
        clase_formulario = configuracion["edit_form"]
    elif accion == "password" and modelo is Usuario:
        if not request.user.has_perm(permiso(modelo, "change")):
            raise PermissionDenied
        objeto = get_object_or_404(modelo, pk=request.POST.get("registro"))
        formulario = SetPasswordForm(
            objeto,
            request.POST,
            prefix=f"contrasena-{objeto.pk}",
        )
        if formulario.is_valid():
            formulario.save()
            messages.success(request, "La contraseña se actualizó correctamente.")
            return redirect(f"{request.path}#registros")
        formularios[(clave, "password", str(objeto.pk))] = formulario
        formulario_abierto = (clave, "edit", str(objeto.pk))
    elif accion == "bulk":
        campo = configuracion.get("bulk_field")
        estado = request.POST.get("estado")
        ids = request.POST.getlist("registros")
        if not campo or estado not in {"0", "1"} or not ids:
            messages.warning(request, "No seleccionaste ningún registro para cambiar de estado.")
            return redirect(f"{request.path}#registros")
        if not request.user.has_perm(permiso(modelo, "change")):
            raise PermissionDenied
        
        objetivos = modelo.objects.filter(pk__in=ids)
        omitidos = 0
        cambios = {campo: estado == "1"}
        if modelo is Producto and campo == "activo" and estado == "1":
            omitidos = objetivos.incompletos().count()
            objetivos = objetivos.completos()
            # Publicar un borrador completo también lo saca de borrador;
            # si no, quedaría "activo" pero invisible en la tienda.
            cambios["es_borrador"] = False

        actualizados = objetivos.update(**cambios)
        messages.success(
            request,
            f"Se actualizaron {actualizados} registros seleccionados.",
        )
        if omitidos:
            messages.warning(
                request,
                f"{omitidos} producto(s) no se activaron porque les falta "
                "nombre, código, imagen o un precio mayor a cero.",
            )
        return redirect(f"{request.path}#registros")
    elif accion == "delete":
        if not configuracion.get("deletable", True):
            raise PermissionDenied("Este registro no se puede eliminar.")
        if not request.user.has_perm(permiso(modelo, "delete")):
            raise PermissionDenied
        objeto = get_object_or_404(modelo, pk=request.POST.get("registro"))
        try:
            objeto.delete()
        except ProtectedError:
            messages.error(
                request,
                "No se puede borrar porque otro registro todavía lo necesita.",
            )
        else:
            messages.success(request, "Registro eliminado.")
        return redirect(f"{request.path}#registros")
    else:
        raise PermissionDenied("La acción solicitada no está disponible.")

    if accion in {"create", "edit"}:
        prefijo = f"{clave}-nuevo" if objeto is None else f"{clave}-{objeto.pk}"
        formulario = preparar_formulario(
            clase_formulario(
                request.POST,
                request.FILES,
                instance=objeto,
                prefix=prefijo,
            ),
            request.user,
        )

        variante_formset = None
        if modelo is Producto and accion == "edit":
            variante_formset = VarianteFormSet(
                request.POST,
                instance=objeto,
                prefix=f"variantes-{objeto.pk}"
            )

        if formulario.is_valid() and (variante_formset is None or variante_formset.is_valid()):
            guardado = formulario.save(commit=False)
            if hasattr(guardado, "actualizado_por"):
                guardado.actualizado_por = request.user
            if hasattr(guardado, "subido_por") and not guardado.subido_por_id:
                guardado.subido_por = request.user
            guardado.save()
            formulario.save_m2m()

            if variante_formset:
                variante_formset.save()

            messages.success(request, "Los cambios se guardaron correctamente.")
            return redirect(f"{request.path}#registros")

        registro = str(objeto.pk) if objeto else ""
        formularios[(clave, accion, registro)] = formulario
        if variante_formset:
            formularios[(clave, "formset", registro)] = variante_formset
        formulario_abierto = (clave, accion, registro)

    return formularios, formulario_abierto


@staff_member_required
def admin_dashboard(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    
    recursos = recursos_visibles(request.user)
    return render(
        request,
        "admin_custom/index.html",
        {"recursos": recursos, "menu_lateral": construir_menu(recursos), "migas": construir_migas()},
    )


@staff_member_required
def admin_section(request, seccion):
    configuracion = next(
        (item for item in RECURSOS if item["key"] == seccion),
        None,
    )
    if configuracion is None:
        raise PermissionDenied("El módulo solicitado no está disponible.")
    if not request.user.has_perm(permiso(configuracion["model"], "view")):
        raise PermissionDenied

    if request.method == "POST":
        resultado = procesar_accion(request, seccion, configuracion)
        if isinstance(resultado, HttpResponse):
            return resultado
        formularios, formulario_abierto = resultado
    elif request.method == "GET":
        formularios = {}
        formulario_abierto = None
        if configuracion["model"] is Producto and request.GET.get(PARAMETRO_GALERIA):
            formulario_abierto = (seccion, "edit", request.GET[PARAMETRO_GALERIA])
    else:
        return HttpResponseNotAllowed(["GET", "POST"])

    contexto = crear_contexto(
        request,
        seccion,
        formularios,
        formulario_abierto,
    )
    return render(
        request,
        "admin_custom/section.html",
        contexto,
    )