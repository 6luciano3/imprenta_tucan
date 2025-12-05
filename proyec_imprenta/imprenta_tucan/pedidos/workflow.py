# Automatización del workflow de estados del pedido
from .models import Pedido, EstadoPedido


def avanzar_estado_pedido(pedido: Pedido):
    # Lógica para avanzar automáticamente el estado del pedido
    # Ejemplo: de 'pendiente' a 'proceso', de 'proceso' a 'finalizado', etc.
    return pedido
