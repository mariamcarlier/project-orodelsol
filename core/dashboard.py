"""Gestión CRUD de los modelos del proyecto desde una sola pantalla."""

from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseNotAllowed
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from configuracion.forms import (
    IdiomaForm,
    ImpuestoForm,
    MonedaForm,
    ParametroGeneralForm,
)
from configuracion.models import Idioma, Impuesto, Moneda, ParametroGeneral
from usuarios.forms import AdministrarUsuarioForm, RegistroUsuarioForm
from usuarios.models import Usuario

from .models import Coleccion, Producto


class GrupoPermisosForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ("name", "permissions")


class AdministrarUsuarioCreacionForm(RegistroUsuarioForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label="Grupos y permisos",
    )

    class Meta(RegistroUsuarioForm.Meta):
        fields = (*RegistroUsuarioForm.Meta.fields, "groups")


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = (
            "nombre",
            "coleccion",
            "detalle",
            "descripcion",
            "precio",
            "imagen_url",
            "destacado",
            "activo",
        )


class ColeccionForm(forms.ModelForm):
    class Meta:
        model = Coleccion
        fields = ("nombre", "descripcion", "temporada", "imagen_url", "activa")


RECURSOS = (
    {
        "key": "productos",
        "title": "Productos",
        "model": Producto,
        "create_form": ProductoForm,
        "edit_form": ProductoForm,
        "columns": (
            ("Nombre", "nombre"),
            ("Colección", "coleccion__nombre"),
            ("Precio", "precio"),
            ("Activo", "activo"),
        ),
        "search_fields": ("nombre__icontains", "detalle__icontains"),
        "bulk_field": "activo",
    },
    {
        "key": "colecciones",
        "title": "Colecciones",
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
        "model": Group,
        "create_form": GrupoPermisosForm,
        "edit_form": GrupoPermisosForm,
        # Los permisos del grupo permiten asignar capacidades por modelo.
        "columns": (
            ("Nombre del grupo", "name"),
            ("Permisos asignados", "permissions__count"),
        ),
        "search_fields": ("name__icontains",),
    },
    {
        "key": "impuestos",
        "title": "Impuestos",
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
)


def permiso(modelo, accion):
    return f"{modelo._meta.app_label}.{accion}_{modelo._meta.model_name}"


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
        clase = (
            "dashboard-checkbox"
            if getattr(campo.widget, "input_type", None) == "checkbox"
            else "dashboard-input"
        )
        campo.widget.attrs.setdefault("class", clase)
    return formulario


def crear_contexto(request, clave, formularios=None, formulario_abierto=None):
    formularios = formularios or {}
    menu = [
        {"key": item["key"], "title": item["title"]}
        for item in RECURSOS
        if request.user.has_perm(permiso(item["model"], "view"))
    ]
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
    if modelo is ParametroGeneral:
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
    return {"recursos": menu, "recurso": recurso}


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
            raise PermissionDenied("Selecciona registros y una acción válida.")
        if not request.user.has_perm(permiso(modelo, "change")):
            raise PermissionDenied
        actualizados = modelo.objects.filter(pk__in=ids).update(
            **{campo: estado == "1"}
        )
        messages.success(
            request,
            f"Se actualizaron {actualizados} registros seleccionados.",
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
        if formulario.is_valid():
            guardado = formulario.save(commit=False)
            if isinstance(guardado, ParametroGeneral):
                guardado.actualizado_por = request.user
            guardado.save()
            formulario.save_m2m()
            messages.success(request, "Los cambios se guardaron correctamente.")
            return redirect(f"{request.path}#registros")

        registro = str(objeto.pk) if objeto else ""
        formularios[(clave, accion, registro)] = formulario
        formulario_abierto = (clave, accion, registro)

    return formularios, formulario_abierto


@staff_member_required
def admin_dashboard(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    recursos = [
        {"key": item["key"], "title": item["title"]}
        for item in RECURSOS
        if request.user.has_perm(permiso(item["model"], "view"))
    ]
    return render(request, "admin_custom/index.html", {"recursos": recursos})


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
        f"admin_custom/sections/{seccion}.html",
        contexto,
    )
