"""
Signals de la app automatizacion.

FeedbackRecomendacion.post_save → actualiza pesos del motor PI-2.

Cuando el administrador registra un FeedbackRecomendacion con deltas de criterios,
los pesos del ProveedorInteligenteEngine se ajustan automáticamente y persisten
en ProveedorParametro (BD), sin necesidad de intervención manual.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='automatizacion.FeedbackRecomendacion')
def feedback_recomendacion_actualiza_pesos(sender, instance, created, **kwargs):
    """
    Dispatch: al guardar un FeedbackRecomendacion, aplica los deltas de criterios
    al ProveedorInteligenteEngine para que los pesos se ajusten en BD.

    Solo actúa si al menos un campo feedback_* tiene valor distinto de cero.
    """
    deltas = {
        'precio':         float(instance.feedback_precio or 0),
        'cumplimiento':   float(instance.feedback_cumplimiento or 0),
        'incidencias':    float(instance.feedback_incidencias or 0),
        'disponibilidad': float(instance.feedback_disponibilidad or 0),
    }
    if not any(v != 0.0 for v in deltas.values()):
        return  # sin deltas → nada que ajustar

    try:
        from core.motor.proveedor_engine import ProveedorInteligenteEngine
        ProveedorInteligenteEngine().retroalimentar(deltas)
    except Exception:
        pass  # fallo silencioso: el feedback ya quedó guardado en BD
