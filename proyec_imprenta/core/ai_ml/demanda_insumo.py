"""
Motor ML de predicción de demanda de insumos.

Predice el consumo mensual de un insumo a partir de su historial reciente,
aprendiendo la tendencia/estacionalidad desde los pares de períodos en BD.

Features (en orden de entrenamiento):
    consumo_mes_1  — cantidad consumida el mes anterior.
    consumo_mes_2  — cantidad consumida hace 2 meses.
    consumo_mes_3  — cantidad consumida hace 3 meses.
    tipo_directo   — 1 si el insumo es tipo 'directo', 0 si 'indirecto'.

Target: consumo del mes siguiente.
Model: Ridge regression (robusto con pocos datos de series temporales cortas).
"""
import logging
import os
import pickle

import numpy as np

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'modelo_demanda_insumo.pkl')
FEATURES = ['consumo_mes_1', 'consumo_mes_2', 'consumo_mes_3', 'tipo_directo']

_model = None
_warned_missing = False


def cargar_modelo():
    global _model, _warned_missing
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            if not _warned_missing:
                _warned_missing = True
                logger.warning(
                    "Motor ML de demanda de insumos INACTIVO: modelo no encontrado en '%s'. "
                    "Ejecuta: python manage.py entrenar_modelo_demanda_insumo",
                    MODEL_PATH,
                )
            raise FileNotFoundError(MODEL_PATH)
        with open(MODEL_PATH, 'rb') as f:
            _model = pickle.load(f)
    return _model


def predecir_demanda_ml(insumo_id: int, periodo_actual: str) -> float | None:
    """
    Predice la demanda del insumo para el período indicado usando el modelo ML.

    Recupera los 3 meses previos de ConsumoRealInsumo como features.
    Si no hay datos suficientes devuelve None para que el llamador use
    el fallback de media móvil.

    Args:
        insumo_id:       PK del Insumo.
        periodo_actual:  Período objetivo 'YYYY-MM'.

    Returns:
        float  — cantidad predicha (≥ 0), o None si modelo ausente / sin historial.
    """
    try:
        model = cargar_modelo()
    except FileNotFoundError:
        return None

    try:
        from insumos.models import Insumo, ConsumoRealInsumo
        insumo = Insumo.objects.get(idInsumo=insumo_id)

        año, mes = map(int, periodo_actual.split('-'))
        periodos_prev = []
        for i in range(1, 4):
            m = mes - i
            y = año
            if m <= 0:
                m += 12
                y -= 1
            periodos_prev.append(f"{y:04d}-{m:02d}")

        qs = (
            ConsumoRealInsumo.objects
            .filter(insumo_id=insumo_id, periodo__in=periodos_prev)
            .values('periodo', 'cantidad_consumida')
        )
        por_periodo = {}
        for row in qs:
            por_periodo[row['periodo']] = (
                por_periodo.get(row['periodo'], 0) + row['cantidad_consumida']
            )

        consumos = [float(por_periodo.get(p, 0)) for p in periodos_prev]
        # Si los tres meses previos son cero, no hay base para predecir
        if sum(consumos) == 0:
            return None

        tipo_directo = 1.0 if insumo.tipo == 'directo' else 0.0
        X = np.array([[consumos[0], consumos[1], consumos[2], tipo_directo]])
        pred = model.predict(X)
        return float(max(0.0, round(pred[0])))
    except Exception as e:
        logger.debug('predecir_demanda_ml fallo para insumo %s: %s', insumo_id, e)
        return None
