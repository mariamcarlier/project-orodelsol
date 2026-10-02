from django.urls import path
from . import views

app_name = 'configuracion'

urlpatterns = [

    # ── CFG-01 Parámetros Generales ───────────────────────────
    path('',                 views.parametros_view, name='configuracion_home'),
    path('parametros/',      views.parametros_view, name='parametros'),

    # ── CFG-02 Impuestos ──────────────────────────────────────
    # Con FBV: la función se referencia directamente, sin .as_view()
    path('impuestos/',       views.impuesto_list,   name='impuesto_list'),
    path('impuestos/nuevo/', views.impuesto_create, name='impuesto_create'),

    # ── CFG-03 Monedas ────────────────────────────────────────
    path('monedas/',         views.moneda_list,     name='moneda_list'),
    path('monedas/nuevo/',   views.moneda_create,   name='moneda_create'),

    # ── CFG-04 Idiomas ────────────────────────────────────────
    path('idiomas/',         views.idioma_list,     name='idioma_list'),
    path('idiomas/nuevo/',   views.idioma_create,   name='idioma_create'),

]