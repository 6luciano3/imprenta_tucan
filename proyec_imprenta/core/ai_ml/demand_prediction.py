# Predicción de demanda de insumos


def predecir_demanda(insumo_id: int, historico=None) -> int:
    """
    Predice la demanda del insumo para el período actual usando media móvil.

    Algoritmo: media simple de ConsumoRealInsumo de los últimos 3 meses.
    Fallback: stock_minimo_sugerido calculado a partir del consumo promedio mensual.

    Args:
        insumo_id: PK del Insumo.
        historico: ignorado (compatibilidad). Se usa ConsumoRealInsumo de BD.

    Returns:
        Cantidad entera predicha (0 si no hay ningún dato disponible).
    """
    try:
        from django.utils import timezone
        from insumos.models import Insumo, predecir_demanda_media_movil
        periodo = timezone.now().strftime('%Y-%m')
        insumo = Insumo.objects.get(idInsumo=insumo_id)
        cantidad = predecir_demanda_media_movil(insumo, periodo, meses=3)
        if cantidad is not None:
            return int(cantidad)
        return int(insumo.stock_minimo_sugerido or 0)
    except Exception:
        return 0
