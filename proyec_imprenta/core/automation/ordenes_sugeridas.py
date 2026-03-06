"""
Generación de órdenes de compra sugeridas a partir de un pedido.

Analiza los insumos necesarios para completar un pedido y genera borradores
de OrdenCompra para los que tienen stock insuficiente, recomendando el
mejor proveedor disponible.
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def generar_orden_sugerida(pedido_id: int) -> dict:
    """
    Genera one o más borradores de OrdenCompra para el pedido dado.

    Proceso:
        1. Obtiene los insumos requeridos para el pedido (via calcular_consumo_pedido).
        2. Para cada insumo con stock insuficiente:
           a. Determina la cantidad a comprar (cantidad_compra_sugerida o faltante).
           b. Recomienda el mejor proveedor (PI-2).
           c. Crea un borrador de OrdenCompra (estado='sugerida').
           d. Registra en CompraPropuesta para aprobación humana.

    Returns:
        {
            'pedido_id': int,
            'ordenes_generadas': int,
            'detalle': list of dicts,
        }
    """
    try:
        from pedidos.models import Pedido
        pedido = Pedido.objects.select_related('producto').get(pk=pedido_id)
    except Exception as exc:
        logger.warning('generar_orden_sugerida: pedido %s no encontrado — %s', pedido_id, exc)
        return {'pedido_id': pedido_id, 'ordenes_generadas': 0, 'error': str(exc), 'detalle': []}

    try:
        from pedidos.services import calcular_consumo_pedido, verificar_stock_consumo
        consumo = calcular_consumo_pedido(pedido)
        ok, faltantes = verificar_stock_consumo(consumo)
    except Exception as exc:
        logger.error('generar_orden_sugerida: error calculando consumo — %s', exc)
        return {'pedido_id': pedido_id, 'ordenes_generadas': 0, 'error': str(exc), 'detalle': []}

    if ok:
        return {'pedido_id': pedido_id, 'ordenes_generadas': 0, 'detalle': [], 'mensaje': 'Stock suficiente'}

    ordenes_generadas = []

    for insumo_id, cantidad_faltante in faltantes.items():
        try:
            from insumos.models import Insumo
            insumo = Insumo.objects.get(idInsumo=insumo_id)
        except Exception:
            continue

        # Cantidad a comprar: prioriza la sugerida en BD, luego el faltante
        cantidad_req = insumo.cantidad_compra_sugerida or int(cantidad_faltante)

        # Recomendar mejor proveedor vía PI-2
        proveedor = None
        try:
            from automatizacion.api.services import ProveedorInteligenteService
            proveedor = ProveedorInteligenteService.recomendar_proveedor(insumo)
        except Exception:
            proveedor = insumo.proveedor  # fallback al proveedor actual

        try:
            from django.db import transaction
            from pedidos.models import OrdenCompra
            from automatizacion.models import CompraPropuesta

            with transaction.atomic():
                oc = OrdenCompra.objects.create(
                    insumo=insumo,
                    cantidad=cantidad_req,
                    proveedor=proveedor,
                    estado='sugerida',
                    comentario=f'Generada automáticamente por pedido #{pedido_id}',
                )
                try:
                    CompraPropuesta.objects.create(
                        insumo=insumo,
                        cantidad_requerida=cantidad_req,
                        proveedor_recomendado=proveedor,
                        motivo_trigger='pedido_insuficiente',
                        estado='pendiente',
                        borrador_oc=oc,
                    )
                except Exception:
                    pass

            ordenes_generadas.append({
                'insumo_id': insumo_id,
                'insumo': insumo.nombre,
                'cantidad_solicitada': cantidad_req,
                'proveedor': str(proveedor) if proveedor else 'sin proveedor',
                'orden_id': oc.pk,
            })
            logger.info('Orden sugerida creada: insumo=%s, cantidad=%s, proveedor=%s', insumo.nombre, cantidad_req, proveedor)

        except Exception as exc:
            logger.error('generar_orden_sugerida: error creando OrdenCompra — %s', exc)

    return {
        'pedido_id': pedido_id,
        'ordenes_generadas': len(ordenes_generadas),
        'detalle': ordenes_generadas,
    }

