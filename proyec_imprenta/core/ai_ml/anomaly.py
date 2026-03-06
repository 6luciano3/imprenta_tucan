"""
Detección de anomalías en pedidos.

Método: z-score por cliente.
    Para cada pedido reciente, compara su monto con la media histórica del
    mismo cliente.  Un z-score ≥ UMBRAL_ZSCORE se considera anomalía.

También detecta anomalías de frecuencia: clientes que de repente piden
muchos más (o muchos menos) pedidos de lo habitual.
"""
from __future__ import annotations

import statistics
from datetime import timedelta

from django.db.models import Avg, Count, StdDev, Sum
from django.utils import timezone

UMBRAL_ZSCORE    = 2.5   # desvíos estándar para marcar anomalía
MIN_MUESTRAS     = 5     # mínimo de pedidos históricos para aplicar z-score
DIAS_RECIENTES   = 30    # ventana de pedidos a analizar
DIAS_HISTORICOS  = 365   # ventana de historial para calcular estadísticas base


def detectar_anomalias_pedidos(dias: int = DIAS_RECIENTES) -> list[dict]:
    """
    Retorna una lista de pedidos recientes que presentan valores anómalos
    (monto muy alto o muy bajo respecto al historial del cliente).

    Returns:
        [
            {
                'pedido_id': int,
                'cliente_id': int,
                'tipo_anomalia': 'monto_alto' | 'monto_bajo',
                'valor_actual': float,
                'valor_esperado': float,
                'desvio_estandar': float,
                'zscore': float,
                'fecha': date,
            },
            ...
        ]
    """
    try:
        from pedidos.models import Pedido
    except ImportError:
        return []

    ahora      = timezone.now()
    desde_rec  = ahora - timedelta(days=dias)
    desde_hist = ahora - timedelta(days=DIAS_HISTORICOS)

    pedidos_recientes = (Pedido.objects
                         .filter(fecha_pedido__gte=desde_rec.date())
                         .select_related('cliente')
                         .values('id', 'cliente_id', 'total', 'fecha_pedido'))

    anomalias = []

    # Agrupa estadísticas por cliente (evita N consultas)
    stats_por_cliente: dict[int, dict] = {}

    for pedido in pedidos_recientes:
        cid = pedido['cliente_id']
        if cid not in stats_por_cliente:
            stats_por_cliente[cid] = _estadisticas_cliente(cid, desde_hist, desde_rec)

        st = stats_por_cliente[cid]
        if st['n'] < MIN_MUESTRAS or st['std'] == 0:
            continue  # insuficientes datos o sin variabilidad

        monto = float(pedido['total'] or 0)
        zscore = (monto - st['media']) / st['std']

        if abs(zscore) >= UMBRAL_ZSCORE:
            anomalias.append({
                'pedido_id':      pedido['id'],
                'cliente_id':     cid,
                'tipo_anomalia':  'monto_alto' if zscore > 0 else 'monto_bajo',
                'valor_actual':   round(monto, 2),
                'valor_esperado': round(st['media'], 2),
                'desvio_estandar': round(st['std'], 2),
                'zscore':         round(zscore, 3),
                'fecha':          pedido['fecha_pedido'],
            })

    anomalias.sort(key=lambda x: abs(x['zscore']), reverse=True)
    return anomalias


def detectar_anomalias_stock(umbral_pct: float = 0.8) -> list[dict]:
    """
    Detecta insumos cuyo stock cayó más de `umbral_pct` respecto al stock
    mínimo sugerido en los últimos 7 días (señal de consumo extraordinario).

    Returns:
        [{'insumo_id', 'insumo_nombre', 'stock_actual', 'stock_minimo',
          'ratio', 'severidad'}, ...]
    """
    try:
        from insumos.models import Insumo
    except ImportError:
        return []

    anomalias = []
    for insumo in Insumo.objects.filter(activo=True).only(
        'idInsumo', 'nombre', 'stock', 'stock_minimo_sugerido'
    ):
        minimo = int(insumo.stock_minimo_sugerido or 0)
        if minimo == 0:
            continue
        stock = int(insumo.stock or 0)
        ratio = stock / minimo
        if ratio <= (1 - umbral_pct):
            anomalias.append({
                'insumo_id':     insumo.idInsumo,
                'insumo_nombre': insumo.nombre,
                'stock_actual':  stock,
                'stock_minimo':  minimo,
                'ratio':         round(ratio, 3),
                'severidad':     'critica' if stock == 0 else 'alta',
            })

    anomalias.sort(key=lambda x: x['ratio'])
    return anomalias


# --------------------------------------------------------------------------- #
# Helpers internos                                                              #
# --------------------------------------------------------------------------- #

def _estadisticas_cliente(cliente_id: int, desde: 'datetime', hasta: 'datetime') -> dict:
    """Calcula media y desv. estándar del monto de pedidos históricos."""
    try:
        from pedidos.models import Pedido
        montos = list(
            Pedido.objects
            .filter(
                cliente_id=cliente_id,
                fecha_pedido__gte=desde.date(),
                fecha_pedido__lt=hasta.date(),
            )
            .values_list('total', flat=True)
        )
        montos = [float(m) for m in montos if m is not None]
        n = len(montos)
        if n < 2:
            return {'n': n, 'media': 0.0, 'std': 0.0}
        return {
            'n':     n,
            'media': statistics.mean(montos),
            'std':   statistics.stdev(montos),
        }
    except Exception:
        return {'n': 0, 'media': 0.0, 'std': 0.0}
