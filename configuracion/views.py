# ═══════════════════════════════════════════════════════════════
# views.py — Vistas del módulo Configuración
#
# Estilo: FBV (Function-Based Views)
#
# ¿Por qué FBV aquí?
# Permite ver explícitamente cada paso del ciclo Django:
#   1. Llega el REQUEST (GET o POST)
#   2. Se consulta la BASE DE DATOS
#   3. Se arma el CONTEXT (diccionario de datos para el HTML)
#   4. Se retorna un RESPONSE (el HTML renderizado)
#
# Estructura de cada vista:
#   GET  → Mostrar datos / formulario vacío
#   POST → Procesar formulario enviado → guardar → redirigir
# ═══════════════════════════════════════════════════════════════

from django.shortcuts import render, redirect
from django.contrib import messages

from .models import Impuesto, Moneda
from .forms  import ImpuestoForm, MonedaForm


# ──────────────────────────────────────────────────────────────
# CFG-02 — IMPUESTOS
# ──────────────────────────────────────────────────────────────

def impuesto_list(request):
    """
    GET /configuracion/impuestos/
    Consulta todos los impuestos en la BD y los envía al template.
    """
    impuestos = Impuesto.objects.all()           # 1. Busca en BD
    context   = {'impuestos': impuestos}         # 2. Empaqueta los datos
    return render(request,                       # 3. Devuelve el HTML
                  'configuracion/impuestos.html',
                  context)


def impuesto_create(request):
    """
    GET  /configuracion/impuestos/nuevo/ → Muestra formulario vacío
    POST /configuracion/impuestos/nuevo/ → Valida y guarda el nuevo impuesto
    """
    if request.method == 'POST':
        # El usuario envió el formulario → intentamos guardar
        form = ImpuestoForm(request.POST)        # 1. Carga los datos enviados

        if form.is_valid():                      # 2. Valida (campos requeridos, tipos, etc.)
            form.save()                          # 3. Guarda en la BD
            messages.success(request, 'Impuesto registrado correctamente.')
            return redirect('configuracion:impuesto_list')  # 4. Redirige a la lista

        # Si el formulario tiene errores, vuelve a mostrarlo con los mensajes de error
        messages.error(request, 'Corrige los errores antes de continuar.')

    else:
        # El usuario llegó por GET → mostramos formulario vacío
        form = ImpuestoForm()

    context = {'form': form}
    return render(request, 'configuracion/impuesto_form.html', context)


# ──────────────────────────────────────────────────────────────
# CFG-03 — MONEDAS
# ──────────────────────────────────────────────────────────────

def moneda_list(request):
    """
    GET /configuracion/monedas/
    Consulta todas las monedas ordenadas: principal primero, luego por código ISO.
    """
    monedas = Moneda.objects.all()               # El orden lo define Meta.ordering del modelo
    context = {'monedas': monedas}
    return render(request, 'configuracion/monedas.html', context)


def moneda_create(request):
    """
    GET  /configuracion/monedas/nuevo/ → Muestra formulario vacío
    POST /configuracion/monedas/nuevo/ → Valida y guarda la nueva moneda
    La lógica de 'moneda principal única' la maneja el modelo en su save().
    """
    if request.method == 'POST':
        form = MonedaForm(request.POST)

        if form.is_valid():
            form.save()   # El save() del modelo desactiva la principal anterior automáticamente
            messages.success(request, 'Moneda registrada correctamente.')
            return redirect('configuracion:moneda_list')

        messages.error(request, 'Corrige los errores antes de continuar.')

    else:
        form = MonedaForm()

    context = {'form': form}
    return render(request, 'configuracion/moneda_form.html', context)