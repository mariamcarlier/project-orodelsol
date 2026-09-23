from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView
from .models import Impuesto

class ImpuestoListView(ListView):# Muestra una lista de objetos desde la base de datos.
    model = Impuesto
    template_name = 'configuracion/impuestos.html'
    context_object_name = 'impuestos'  # Así llamaremos a la lista en el HTML

class ImpuestoCreateView(CreateView):
    model = Impuesto
    fields = ['nombre', 'tasa', 'vigente']  # Campos que tendrá el formulario
    template_name = 'configuracion/impuesto_form.html'
    success_url = reverse_lazy('configuracion:impuesto_list') # A dónde ir tras guardar