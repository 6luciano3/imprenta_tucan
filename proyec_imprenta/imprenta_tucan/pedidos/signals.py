from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Pedido, OrdenProduccion


@receiver(post_save, sender=Pedido)
def crear_orden_produccion(sender, instance, created, **kwargs):
    if created:
        OrdenProduccion.objects.create(pedido=instance)
