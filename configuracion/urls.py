from django.urls import path
from . import views

app_name = 'configuracion'

urlpatterns = [
    # Ruta para ver la lista: /configuracion/impuestos/
    path('impuestos/', views.ImpuestoListView.as_view(), name='impuesto_list'),
    
    # Ruta para crear uno nuevo: /configuracion/impuestos/nuevo/
    path('impuestos/nuevo/', views.ImpuestoCreateView.as_view(), name='impuesto_create'),
]