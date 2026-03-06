"""
Detección de riesgo de churn (pérdida de cliente).

Utiliza reglas heurísticas sobre el historial de pedidos:
    - Días de inactividad desde el último pedido.
    - Tendencia de frecuencia: últimos 3 meses vs. 3 meses previos.
    - Tendencia de valor: monto últimos 3 meses vs. 3 meses previos.

No requiere modelos ML entrenados; funciona con los datos ya disponibles
en la BD.  Para integrar un modelo supervisado en el futuro, reemplazar
`_score_heuristico()` con una llamada al modelo serializado.
"""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone


# --------------------------------------------------------------------------- #
# Thresholds (ajustables desde MotorConfig si se desea)                        #
# --------------------------------------------------------------------------- #
DIAS_INACTIVO_ALTO   = 90   # sin pedidos → riesgo alto
DIAS_INACTIVO_MEDIO  = 45   # sin pedidos → riesgo medio
CAIDA_FREQ_UMBRAL    = 0.5  # frecuencia cayó >50 % → señal negativa
CAIDA_VALOR_UMBRAL   = 0.4  # monto cayó >40 % → señal negativa


def detectar_riesgo_churn(cliente_id: int) -> dict:
    """
    Evalúa el riesgo de pérdida del cliente.

    Returns:
        {
            'cliente_id': int,
            'riesgo': 'alto' | 'medio' | 'bajo',
            'score': float,          # 0.0 (sin riesgo) – 1.0 (máximo riesgo)
            'motivos': list[str],
            'dias_inactivo': int,
            'freq_reciente': int,    # pedidos en los últimos 3 meses
            'freq_anterior': int,    # pedidos en los 3 meses previos
        }
    """
    try:
        from pedidos.models import Pedido
    except ImportError:
        return {'cliente_id': cliente_id, 'riesgo': 'bajo', 'score': 0.0,
                'motivos': ['Sin acceso al modelo Pedido'], 'dias_inactivo': 0,
                'freq_reciente': 0, 'freq_anterior': 0}

    ahora = timezone.now()

    # --- Último pedido ---
    ultimo = (Pedido.objects
              .filter(cliente_id=cliente_id)
              .order_by('-fecha_pedido')
              .values('fecha_pedido')
              .first())
    if not ultimo:
        return {'cliente_id': cliente_id, 'riesgo': 'alto', 'score': 1.0,
                'motivos': ['Sin pedidos registrados'], 'dias_inactivo': -1,
                'freq_reciente': 0, 'freq_anterior': 0}

    dias_inactivo = (ahora.date() - ultimo['fecha_pedido']).days

    # --- Frecuencia y valor por período ---
    hace_3m  = ahora - timedelta(days=90)
    hace_6m  = ahora - timedelta(days=180)

    def _stats(desde, hasta):
        qs = Pedido.objects.filter(
            cliente_id=cliente_id,
            fecha_pedido__gte=desde.date(),
            fecha_pedido__lt=hasta.date(),
        )
        agg = qs.aggregate(total=Count('id'), monto=Sum('total'))
        return agg['total'] or 0, float(agg['monto'] or 0)

    freq_rec,  monto_rec  = _stats(hace_3m, ahora)
    freq_ant,  monto_ant  = _stats(hace_6m, hace_3m)

    # --- Scoring heurístico ---
    score   = 0.0
    motivos = []

    # Inactividad
    if dias_inactivo >= DIAS_INACTIVO_ALTO:
        score  += 0.5
        motivos.append(f'Inactivo hace {dias_inactivo} días (≥ {DIAS_INACTIVO_ALTO})')
    elif dias_inactivo >= DIAS_INACTIVO_MEDIO:
        score  += 0.25
        motivos.append(f'Inactivo hace {dias_inactivo} días (≥ {DIAS_INACTIVO_MEDIO})')

    # Caída de frecuencia
    if freq_ant > 0:
        caida_freq = 1 - freq_rec / freq_ant
        if caida_freq > CAIDA_FREQ_UMBRAL:
            score  += 0.25
            motivos.append(
                f'Frecuencia cayó {caida_freq:.0%} '
                f'({freq_ant} → {freq_rec} pedidos en 3 meses)'
            )
    elif freq_rec == 0:
        score  += 0.15
        motivos.append('Sin pedidos en los últimos 6 meses')

    # Caída de valor
    if monto_ant > 0:
        caida_val = 1 - monto_rec / monto_ant
        if caida_val > CAIDA_VALOR_UMBRAL:
            score  += 0.20
            motivos.append(
                f'Monto cayó {caida_val:.0%} '
                f'(${monto_ant:.0f} → ${monto_rec:.0f})'
            )

    score = min(1.0, score)
    if score >= 0.6:
        riesgo = 'alto'
    elif score >= 0.3:
        riesgo = 'medio'
    else:
        riesgo = 'bajo'

    return {
        'cliente_id':   cliente_id,
        'riesgo':       riesgo,
        'score':        round(score, 3),
        'motivos':      motivos or ['Sin señales de alerta'],
        'dias_inactivo': dias_inactivo,
        'freq_reciente': freq_rec,
        'freq_anterior': freq_ant,
    }


def detectar_churn_masivo(solo_activos: bool = True) -> list[dict]:
    """
    Evalúa el riesgo de churn para todos los clientes activos.

    Returns:
        Lista ordenada de mayor a menor score, excluyendo los de riesgo 'bajo'
        si solo hay pocos con riesgo.
    """
    try:
        from clientes.models import Cliente
    except ImportError:
        return []

    qs = Cliente.objects.all()
    if solo_activos:
        qs = qs.filter(activo=True)

    resultados = []
    for cliente in qs.only('id'):
        try:
            r = detectar_riesgo_churn(cliente.id)
            resultados.append(r)
        except Exception:
            continue

    resultados.sort(key=lambda x: x['score'], reverse=True)
    return resultados
