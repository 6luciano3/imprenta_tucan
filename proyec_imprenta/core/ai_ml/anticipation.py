"""
Anticipación proactiva de compras de insumos críticos.

Detecta ANTES de que el stock caiga al mínimo si una compra será necesaria,
basándose en la tendencia de consumo de los últimos N meses.

Algoritmo:
    1. Recupera consumos mensuales (ConsumoRealInsumo) del insumo.
    2. Calcula tasa de consumo diario (promedio ponderado: meses recientes pesan más).
    3. Estima días hasta agotar stock: stock_actual / consumo_diario.
    4. Compara con lead_time del proveedor + buffer de seguridad.
    5. Si los días restantes < lead_time + buffer → anticipa la compra.

Retorna:
    dict con acción sugerida, o None si no se requiere anticipar.
"""
import logging
from datetime import date

logger = logging.getLogger(__name__)


def anticipar_compras(insumo_id: int, demanda_predicha: float) -> dict | None:
    """
    Evalúa si se debe anticipar una compra para el insumo dado.

    Args:
        insumo_id:        PK del insumo a evaluar.
        demanda_predicha: Demanda estimada para el período actual (media móvil).

    Returns:
        dict  → acción sugerida (ver estructura abajo).
        None  → no se requiere anticipar.

    Estructura del dict retornado:
        {
            'insumo_id':         int,
            'insumo_nombre':     str,
            'stock_actual':      float,
            'consumo_diario':    float,    # promedio ponderado
            'dias_restantes':    float,    # stock_actual / consumo_diario
            'lead_time_dias':    int,      # días de entrega configurados
            'buffer_dias':       int,      # días de seguridad configurados
            'cantidad_sugerida': float,    # cobertura para lead_time + buffer + 30 días extra
            'urgencia':          'critica' | 'alta' | 'media',
            'motivo':            str,
        }
    """
    try:
        from insumos.models import Insumo, ConsumoRealInsumo
        from configuracion.models import Parametro
        from django.utils import timezone
    except ImportError as e:
        logger.error('anticipar_compras: error de importación — %s', e)
        return None

    try:
        insumo = Insumo.objects.get(idInsumo=insumo_id)
    except Insumo.DoesNotExist:
        logger.warning('anticipar_compras: insumo_id=%s no existe', insumo_id)
        return None

    stock_actual = float(insumo.stock or 0)
    stock_minimo = float(insumo.stock_minimo_sugerido or 0)

    # ── Parámetros configurables ─────────────────────────────────────────
    lead_time_dias = int(Parametro.get('ANTICIPACION_LEAD_TIME_DIAS', 7))
    buffer_dias    = int(Parametro.get('ANTICIPACION_BUFFER_DIAS', 5))
    meses_hist     = int(Parametro.get('ANTICIPACION_MESES_HISTORICO', 6))
    # ─────────────────────────────────────────────────────────────────────

    # Consumos de los últimos N meses
    hoy = timezone.now().date()
    periodos = _periodos_anteriores(hoy, meses_hist)
    consumos_qs = (
        ConsumoRealInsumo.objects
        .filter(insumo_id=insumo_id, periodo__in=periodos)
        .values('periodo', 'cantidad_consumida')
    )
    consumos_por_periodo: dict = {}
    for c in consumos_qs:
        consumos_por_periodo[c['periodo']] = (
            consumos_por_periodo.get(c['periodo'], 0) + c['cantidad_consumida']
        )

    # Tasa de consumo diario con decaimiento: meses más recientes pesan más
    # peso = 1 / (1 + antiguedad_meses)
    suma_ponderada = 0.0
    suma_pesos = 0.0
    for i, periodo in enumerate(periodos):  # periodos[0] = más reciente
        cantidad = consumos_por_periodo.get(periodo, 0)
        peso = 1.0 / (1.0 + i)
        dias_mes = 30  # aproximación
        tasa = cantidad / dias_mes
        suma_ponderada += tasa * peso
        suma_pesos += peso

    consumo_diario = suma_ponderada / suma_pesos if suma_pesos > 0 else 0.0

    # Si no hay historial de consumo, usar la demanda predicha / 30
    if consumo_diario == 0 and demanda_predicha > 0:
        consumo_diario = float(demanda_predicha) / 30.0

    if consumo_diario <= 0:
        # Sin consumo histórico ni predicción: no se puede anticipar
        return None

    dias_restantes = stock_actual / consumo_diario
    horizonte_critico = lead_time_dias + buffer_dias

    if dias_restantes >= horizonte_critico + 30:
        # Stock suficiente para más de lead_time + buffer + 30 días
        return None

    # Cantidad sugerida: cubrir lead_time + buffer + 30 días de cobertura extra
    cobertura_dias = lead_time_dias + buffer_dias + 30
    cantidad_sugerida = max(
        consumo_diario * cobertura_dias - stock_actual,
        float(stock_minimo),
        1.0,
    )

    # Clasificar urgencia
    if dias_restantes <= lead_time_dias:
        urgencia = 'critica'
    elif dias_restantes <= horizonte_critico:
        urgencia = 'alta'
    else:
        urgencia = 'media'

    motivo = (
        f'Stock para {dias_restantes:.1f} días; '
        f'lead_time={lead_time_dias}d + buffer={buffer_dias}d. '
        f'Consumo diario ponderado: {consumo_diario:.2f} unidades/día.'
    )

    logger.info(
        'Anticipación detectada para %s (id=%s): %s',
        insumo.nombre, insumo_id, motivo
    )

    return {
        'insumo_id':         insumo_id,
        'insumo_nombre':     insumo.nombre,
        'stock_actual':      stock_actual,
        'consumo_diario':    round(consumo_diario, 4),
        'dias_restantes':    round(dias_restantes, 1),
        'lead_time_dias':    lead_time_dias,
        'buffer_dias':       buffer_dias,
        'cantidad_sugerida': round(cantidad_sugerida, 0),
        'urgencia':          urgencia,
        'motivo':            motivo,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _periodos_anteriores(hoy: date, n: int) -> list[str]:
    """Genera los N períodos YYYY-MM previos al mes actual (más reciente primero)."""
    periodos = []
    anio, mes = hoy.year, hoy.month
    for _ in range(n):
        mes -= 1
        if mes == 0:
            mes = 12
            anio -= 1
        periodos.append(f'{anio:04d}-{mes:02d}')
    return periodos

