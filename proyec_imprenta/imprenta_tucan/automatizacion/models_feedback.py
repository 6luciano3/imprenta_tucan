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
