from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import path


app_name = 'configuracion'

def redirigir_al_panel(request, seccion):
    if request.method not in {"GET", "HEAD"}:
        return HttpResponseNotAllowed(["GET", "HEAD"])
    return redirect("core:admin_section", seccion=seccion)


urlpatterns = [
    path("", redirigir_al_panel, {"seccion": "parametros"}, name="configuracion_home"),
    path("parametros/", redirigir_al_panel, {"seccion": "parametros"}, name="parametros"),
    path("impuestos/", redirigir_al_panel, {"seccion": "impuestos"}, name="impuesto_list"),
    path("impuestos/nuevo/", redirigir_al_panel, {"seccion": "impuestos"}, name="impuesto_create"),
    path("monedas/", redirigir_al_panel, {"seccion": "monedas"}, name="moneda_list"),
    path("monedas/nuevo/", redirigir_al_panel, {"seccion": "monedas"}, name="moneda_create"),
    path("idiomas/", redirigir_al_panel, {"seccion": "idiomas"}, name="idioma_list"),
    path("idiomas/nuevo/", redirigir_al_panel, {"seccion": "idiomas"}, name="idioma_create"),
    path("costos-envio/", redirigir_al_panel, {"seccion": "costos_envio"}, name="costo_envio_list"),
    path("costos-envio/nuevo/", redirigir_al_panel, {"seccion": "costos_envio"}, name="costo_envio_create"),
    path("metodos-pago/", redirigir_al_panel, {"seccion": "metodos_pago"}, name="metodo_pago_list"),
    path("metodos-pago/nuevo/", redirigir_al_panel, {"seccion": "metodos_pago"}, name="metodo_pago_create"),
    path("politicas-comerciales/", redirigir_al_panel, {"seccion": "politicas_comerciales"}, name="politica_comercial_detail"),
    path("plantillas-documentos/", redirigir_al_panel, {"seccion": "plantillas_documentos"}, name="plantilla_documento_list"),
    path("plantillas-documentos/nuevo/", redirigir_al_panel, {"seccion": "plantillas_documentos"}, name="plantilla_documento_create"),
]