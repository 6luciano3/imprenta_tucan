# Predicción de demanda de insumos.
# Usa el modelo ML (modelo_demanda_insumo.pkl) cuando está disponible;
# si no, cae a la media móvil de los últimos 3 meses.


def predecir_demanda(insumo_id: int, historico=None) -> int:
    """
    Predice la demanda del insumo para el período actual.

    Jerarquía:
        1. Modelo ML (Ridge entrenado sobre pares de series temporales).
        2. Media móvil simple de los últimos 3 meses (predecir_demanda_media_movil).
        3. stock_minimo_sugerido como último fallback.

    Args:
        insumo_id: PK del Insumo.
        historico: ignorado (compatibilidad).

    Returns:
        Cantidad entera predicha (0 si no hay ningún dato disponible).
    """
    try:
        from django.utils import timezone
        periodo = timezone.now().strftime('%Y-%m')

        # 1) Intentar con modelo ML
        from core.ai_ml.demanda_insumo import predecir_demanda_ml
        cantidad_ml = predecir_demanda_ml(insumo_id, periodo)
        if cantidad_ml is not None:
            return int(cantidad_ml)

        # 2) Fallback: media móvil
        from insumos.models import Insumo, predecir_demanda_media_movil
        insumo = Insumo.objects.get(idInsumo=insumo_id)
        cantidad = predecir_demanda_media_movil(insumo, periodo, meses=3)
        if cantidad is not None:
            return int(cantidad)

        # 3) Último fallback: stock mínimo sugerido
        return int(insumo.stock_minimo_sugerido or 0)
    except Exception:
        return 0
