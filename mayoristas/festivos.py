"""Cálculo de días hábiles (RN-VM-06).

RN-VM-06 pide responder una solicitud de cotización en **24–48 horas hábiles**. Contar «horas hábiles» sin más es ambiguo, así que este módulo trabaja en días:

- Se descuentan sábados y domingos.
- Se descuentan los festivos y cierres registrados en `DiaNoHabil`.
- Si la tabla está vacía, solo se descuentan los fines de semana. **No se inventan festivos**: un año sin calendario cargado produce un plazo algo más largo, nunca uno más corto, y la pantalla lo advierte.

No hay dependencia de librerías de calendario: son unas pocas líneas y así no se añade nada al `requirements.txt`."""

from datetime import timedelta

from .models import DiaNoHabil

# Horas hábiles comprometidas por RN-VM-06.
SLA_MINIMO_HORAS = 24
SLA_MAXIMO_HORAS = 48
# Un día hábil se estima en 8 horas de trabajo (jornada comercial).
HORAS_POR_DIA_HABIL = 8


def es_habil(fecha, festivos=None):
    """True si `fecha` es de lunes a viernes y no está en `festivos`.

    Args:
        fecha: `date` a comprobar.
        festivos: conjunto de fechas no hábiles. Si es None se consulta la
            base de datos una vez; pásalo si vas a evaluar muchas fechas.
    """
    if fecha.weekday() >= 5:  # 5 = sábado, 6 = domingo
        return False
    if festivos is None:
        festivos = conjunto_festivos(fecha.year)
    return fecha not in festivos


def conjunto_festivos(*anios):
    """Fechas registradas como no hábiles, opcionalmente filtradas por año."""
    consulta = DiaNoHabil.objects.all()
    if anios:
        consulta = consulta.filter(fecha__year__in=[a for a in anios if a])
    return set(consulta.values_list("fecha", flat=True))


def sumar_dias_habiles(inicio, dias):
    """Devuelve la fecha resultante de sumar `dias` hábiles a `inicio`.

    El día de inicio NO cuenta: si una solicitud entra un lunes y se piden 2 días hábiles, el resultado es el miércoles. No se avanza el resultado al
    siguiente día hábil si cae en fin de semana, porque el propio recorrido solo se detiene en días hábiles. """
    
    if dias < 0:
        raise ValueError("Los días hábiles a sumar no pueden ser negativos.")

    fecha = inicio
    festivos = conjunto_festivos(inicio.year, inicio.year + 1)
    restantes = dias
    while restantes > 0:
        fecha += timedelta(days=1)
        if es_habil(fecha, festivos):
            restantes -= 1
    return fecha


def dias_habiles_para_horas(horas):
    """Convierte horas hábiles a días hábiles, redondeando hacia arriba.

    24 h con jornada de 8 h = 3 días hábiles; 48 h = 6 días hábiles.
    """
    if horas <= 0:
        return 1
    return -(-horas // HORAS_POR_DIA_HABIL)  # división entera hacia arriba


def plazo_de_respuesta(desde):
    """Ventana de respuesta (RN-VM-06) para una solicitud recibida en `desde`.

    Returns:
        dict con:
          - ``desde`` y ``hasta``: fechas límite mínima y máxima.
          - ``texto``: frase para pantalla.
          - ``calendario_cargado``: False si no hay festivos registrados para
            el año, para poder avisar de que el plazo es estimado.
    """
    festivos = conjunto_festivos(desde.year, desde.year + 1)
    minimo = sumar_dias_habiles(
        desde, dias_habiles_para_horas(SLA_MINIMO_HORAS)
    )
    maximo = sumar_dias_habiles(
        desde, dias_habiles_para_horas(SLA_MAXIMO_HORAS)
    )
    return {
        "desde": minimo,
        "hasta": maximo,
        "texto": (
            f"Respondemos entre el {minimo:%d/%m/%Y} y el {maximo:%d/%m/%Y} "
            f"({SLA_MINIMO_HORAS}–{SLA_MAXIMO_HORAS} horas hábiles)."
        ),
        "calendario_cargado": bool(festivos),
    }