# Ejemplo: predicción de valor futuro de cliente usando un modelo ML entrenado (pickle)
import logging
import os
import pickle

import numpy as np

logger = logging.getLogger(__name__)

# Ruta al modelo entrenado (debes entrenarlo y exportarlo con scikit-learn)
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'modelo_valor_cliente.pkl')

_model = None
# Bandera para emitir el aviso de modelo ausente una sola vez por proceso,
# evitando inundación del log en cada ciclo de ranking.
_warned_missing = False


def cargar_modelo():
    global _model, _warned_missing
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            if not _warned_missing:
                _warned_missing = True
                logger.warning(
                    "Motor ML de valor de cliente INACTIVO: modelo no encontrado en '%s'. "
                    "El ranking operará sólo con scoring por reglas. "
                    "Para activar el ML, entrena y exporta el modelo a esa ruta.",
                    MODEL_PATH,
                )
            raise FileNotFoundError(MODEL_PATH)
        with open(MODEL_PATH, 'rb') as f:
            _model = pickle.load(f)
    return _model

def predecir_valor_cliente(features_dict):
    """
    features_dict: dict con los features del cliente, por ejemplo:
        {
            'total_compras': 12000,
            'frecuencia': 8,
            'margen': 0.25,
            'ofertas_aceptadas': 3,
            ...
        }
    """
    model = cargar_modelo()
    # Ordenar los features según el entrenamiento
    feature_names = ['total_compras', 'frecuencia', 'margen', 'ofertas_aceptadas']
    X = np.array([[features_dict.get(f, 0) for f in feature_names]])
    pred = model.predict(X)
    return float(pred[0])
