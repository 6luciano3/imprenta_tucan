# Ejemplo: predicción de valor futuro de cliente usando un modelo ML entrenado (pickle)
import pickle
import os
import numpy as np

# Ruta al modelo entrenado (debes entrenarlo y exportarlo con scikit-learn)
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'modelo_valor_cliente.pkl')

_model = None

def cargar_modelo():
    global _model
    if _model is None:
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
