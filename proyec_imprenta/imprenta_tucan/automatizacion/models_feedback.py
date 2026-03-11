from django.db import models
from proveedores.models import Proveedor
from insumos.models import Insumo
from pedidos.models import Pedido
from django.contrib.auth import get_user_model

User = get_user_model()


class FeedbackRecomendacion(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    proveedor_recomendado = models.ForeignKey(
        Proveedor, on_delete=models.SET_NULL, null=True, related_name='feedback_recomendado')
    proveedor_final = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, related_name='feedback_final')
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    decision = models.CharField(max_length=20, choices=[(
        'aceptar', 'Aceptar'), ('modificar', 'Modificar'), ('rechazar', 'Rechazar')])
    comentario = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    # Opcional: campos para feedback de criterios
    feedback_precio = models.FloatField(default=0)
    feedback_cumplimiento = models.FloatField(default=0)
    feedback_incidencias = models.FloatField(default=0)
    feedback_disponibilidad = models.FloatField(default=0)

    def __str__(self):
        return f"Feedback {self.pedido_id} - {self.decision}"


# ─── Signal: conectar FeedbackRecomendacion al motor de proveedores ───────────
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=FeedbackRecomendacion)
def actualizar_pesos_proveedor_por_feedback(sender, instance, created, **kwargs):
    """
    Cuando se guarda un FeedbackRecomendacion, ajusta los pesos del motor
    de proveedores usando los deltas de los 4 criterios.
    Si la decision es 'rechazar', invierte los deltas (penaliza al proveedor recomendado).
    Si la decision es 'aceptar', refuerza los pesos actuales.
    Si la decision es 'modificar', aplica los deltas tal cual.
    """
    try:
        from core.motor.proveedor_engine import ProveedorInteligenteEngine

        factor = 1.0
        if instance.decision == 'rechazar':
            factor = -1.0
        elif instance.decision == 'aceptar':
            factor = 1.0
        elif instance.decision == 'modificar':
            factor = 0.5

        feedback = {
            'precio':         instance.feedback_precio        * factor,
            'cumplimiento':   instance.feedback_cumplimiento  * factor,
            'incidencias':    instance.feedback_incidencias   * factor,
            'disponibilidad': instance.feedback_disponibilidad * factor,
        }

        # Solo retroalimentar si hay al menos un valor no nulo
        if any(v != 0 for v in feedback.values()):
            engine = ProveedorInteligenteEngine()
            engine.retroalimentar(feedback)

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"actualizar_pesos_proveedor_por_feedback: error en feedback #{instance.pk}: {e}"
        )
