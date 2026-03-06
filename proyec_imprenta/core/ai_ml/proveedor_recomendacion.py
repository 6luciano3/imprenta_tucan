# Recomendación de proveedores óptimos.
# Usa el modelo ML (modelo_score_proveedor.pkl) cuando está disponible;
# si no, delega a ProveedorInteligenteEngine (scoring por reglas).


def recomendar_proveedor(insumo_id=None):
    """
    Recomienda el mejor proveedor activo.

    Intenta usar el modelo ML para calcular el score de cada proveedor
    (5 features: precio_relativo, cumplimiento, incidencias, disponibilidad, latencia).
    Si el pkl no existe, cae al motor de reglas.

    Args:
        insumo_id: PK del Insumo para evaluar en contexto (None = global).

    Returns:
        Instancia del Proveedor recomendado, o None si no hay proveedores activos.
    """
    try:
        from proveedores.models import Proveedor
        from core.motor.proveedor_engine import ProveedorInteligenteEngine
        from core.ai_ml.score_proveedor import predecir_score_proveedor

        insumo = None
        if insumo_id is not None:
            from insumos.models import Insumo
            insumo = Insumo.objects.get(idInsumo=insumo_id)

        engine = ProveedorInteligenteEngine()
        proveedores = list(Proveedor.objects.filter(activo=True))
        if not proveedores:
            return None

        mejor = None
        mejor_score = -1.0
        for p in proveedores:
            try:
                feats = {
                    'precio_relativo':  engine._precio_relativo(p, insumo),
                    'cumplimiento':     engine._cumplimiento(p),
                    'incidencias':      engine._incidencias(p),
                    'disponibilidad':   engine._disponibilidad(p, insumo),
                    'latencia':         engine._latencia_promedio_dias(p),
                }
                score = predecir_score_proveedor(feats)
            except FileNotFoundError:
                # Fallback a reglas si el modelo no está entrenado
                score = engine.calcular_score(p, insumo)
            except Exception:
                score = engine.calcular_score(p, insumo)

            if score > mejor_score:
                mejor_score = score
                mejor = p
        return mejor
    except Exception:
        return None

