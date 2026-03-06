# Recomendación de proveedores óptimos — delega a ProveedorInteligenteEngine (PI-2)


def recomendar_proveedor(insumo_id=None):
    """
    Recomienda el mejor proveedor activo usando ProveedorInteligenteEngine.

    Args:
        insumo_id: PK del Insumo para evaluar en contexto de ese insumo.
                   None = score global promedio sobre todos los insumos del proveedor.

    Returns:
        Instancia del Proveedor recomendado, o None si no hay proveedores activos.
    """
    try:
        from core.motor.proveedor_engine import ProveedorInteligenteEngine
        insumo = None
        if insumo_id is not None:
            from insumos.models import Insumo
            insumo = Insumo.objects.get(idInsumo=insumo_id)
        engine = ProveedorInteligenteEngine()
        proveedor, _score = engine.recomendar(insumo=insumo)
        return proveedor
    except Exception:
        return None

