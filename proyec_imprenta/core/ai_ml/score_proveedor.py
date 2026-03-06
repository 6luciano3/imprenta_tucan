"""
Motor ML de score de proveedor.

Predice el score [0, 100] de un proveedor a partir de sus 5 métricas
de rendimiento, reemplazando la fórmula de pesos fijos por un modelo
entrenado con datos históricos.

Features (en orden de entrenamiento):
    precio_relativo   — 0.0 (más barato) a 1.0 (más caro).
    cumplimiento      — ratio ponderado de órdenes confirmadas [0, 1].
    incidencias       — ratio ponderado de órdenes rechazadas [0, 1].
    disponibilidad    — ratio consultas de stock positivas [0, 1].
    latencia          — latencia normalizada [0, 1] (0 = rápido).

Model: GradientBoostingRegressor.
"""
import logging
import os
import pickle

import numpy as np

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'modelo_score_proveedor.pkl')
FEATURES = ['precio_relativo', 'cumplimiento', 'incidencias', 'disponibilidad', 'latencia']

_model = None
_warned_missing = False


def cargar_modelo():
    global _model, _warned_missing
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            if not _warned_missing:
                _warned_missing = True
                logger.warning(
                    "Motor ML de proveedores INACTIVO: modelo no encontrado en '%s'. "
                    "Ejecuta: python manage.py entrenar_modelo_score_proveedor",
                    MODEL_PATH,
                )
            raise FileNotFoundError(MODEL_PATH)
        with open(MODEL_PATH, 'rb') as f:
            _model = pickle.load(f)
    return _model


def predecir_score_proveedor(features_dict: dict) -> float:
    """
    Predice el score de un proveedor con el modelo ML.

    Args:
        features_dict: dict con claves precio_relativo, cumplimiento,
                       incidencias, disponibilidad, latencia.

    Returns:
        float en [0, 100], o lanza FileNotFoundError si no hay modelo.
    """
    model = cargar_modelo()
    X = np.array([[features_dict.get(f, 0.5) for f in FEATURES]])
    pred = model.predict(X)
    return float(np.clip(pred[0], 0.0, 100.0))
