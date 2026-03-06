"""
Confirmación de disponibilidad de insumos.

Verifica si hay stock suficiente del insumo en la BD y, si el proveedor tiene
una URL de API configurada, consulta disponibilidad en tiempo real.
"""
import logging

logger = logging.getLogger(__name__)


def confirmar_disponibilidad(insumo_id: int, cantidad: int) -> dict:
    """
    Verifica si hay disponibilidad para `cantidad` unidades del insumo.

    Pasos:
        1. Stock propio en BD (respuesta inmediata).
        2. Si no hay stock suficiente y el proveedor tiene api_stock_url,
           consulta disponibilidad externa vía HTTP POST.

    Returns:
        {
            'disponible': bool,
            'fuente': 'stock_propio' | 'api_proveedor' | 'sin_datos',
            'stock_actual': int,
            'cantidad_solicitada': int,
            'detalle': str,
        }
    """
    try:
        from insumos.models import Insumo
        insumo = Insumo.objects.get(idInsumo=insumo_id)
    except Exception as exc:
        logger.warning('confirmar_disponibilidad: insumo %s no encontrado — %s', insumo_id, exc)
        return {
            'disponible': False, 'fuente': 'sin_datos',
            'stock_actual': 0, 'cantidad_solicitada': cantidad,
            'detalle': f'Insumo no encontrado: {exc}',
        }

    stock_actual = int(insumo.stock or 0)

    # 1) Verificación por stock propio
    if stock_actual >= cantidad:
        return {
            'disponible': True, 'fuente': 'stock_propio',
            'stock_actual': stock_actual, 'cantidad_solicitada': cantidad,
            'detalle': f'Stock propio suficiente ({stock_actual} ≥ {cantidad}).',
        }

    # 2) Consulta a API del proveedor (si está configurada)
    proveedor = getattr(insumo, 'proveedor', None)
    api_url = getattr(proveedor, 'api_stock_url', None) if proveedor else None

    if api_url:
        try:
            import requests
            resp = requests.post(
                api_url,
                json={'insumo_id': insumo_id, 'cantidad': cantidad},
                timeout=10,
            )
            data = resp.json()
            estado = data.get('estado', '').lower()
            detalle = data.get('detalle', '')
            disponible = estado in ('disponible', 'parcial')

            # Registrar consulta en BD
            try:
                from automatizacion.models import ConsultaStockProveedor
                ConsultaStockProveedor.objects.create(
                    proveedor=proveedor,
                    insumo=insumo,
                    cantidad=cantidad,
                    estado=estado or 'consultado',
                    respuesta={'estado': estado, 'detalle': detalle},
                )
            except Exception:
                pass

            return {
                'disponible': disponible, 'fuente': 'api_proveedor',
                'stock_actual': stock_actual, 'cantidad_solicitada': cantidad,
                'detalle': detalle or f'Respuesta API: {estado}',
            }
        except Exception as exc:
            logger.error('confirmar_disponibilidad: error API proveedor — %s', exc)

    # Sin stock propio y sin API: no disponible
    faltante = cantidad - stock_actual
    return {
        'disponible': False, 'fuente': 'stock_propio',
        'stock_actual': stock_actual, 'cantidad_solicitada': cantidad,
        'detalle': f'Stock insuficiente (faltan {faltante} unidades). Sin API de proveedor configurada.',
    }

