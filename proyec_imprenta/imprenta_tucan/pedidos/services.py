from decimal import Decimal
from collections import defaultdict
import math


def calcular_consumo_producto(producto, cantidad: int) -> dict:
    """Calcula consumo para un producto combinando:
    - Receta/BOM (ProductoInsumo)
    - Fórmulas específicas (papel y tinta) si el producto tiene parámetros configurados
    Retorna dict {insumo_id: Decimal(cantidad_requerida)}.
    """
    from productos.models import ProductoInsumo

    req = defaultdict(Decimal)
    if not producto or not cantidad:
        return req
    # 1) Receta estática
    for r in ProductoInsumo.objects.filter(producto=producto).only("insumo_id", "cantidad_por_unidad"):
        req[r.insumo_id] += Decimal(r.cantidad_por_unidad) * Decimal(cantidad)

    # 2) Fórmulas de imprenta (opcionales)
    # Papel
    try:
        up = int(producto.unidades_por_pliego or 0)
        mp = Decimal(producto.merma_papel or 0)
        papel_insumo = getattr(producto, 'papel_insumo', None)
        if up > 0 and producto.papel_insumo_id:
            pliegos_base = Decimal(Decimal(cantidad) / Decimal(up))
            factor_papel = Decimal(1) + mp
            pliegos_necesarios = Decimal(math.ceil(pliegos_base * factor_papel))
            req[producto.papel_insumo_id] += pliegos_necesarios
    except Exception:
        pass

    # Tinta
    try:
        gp = Decimal(producto.gramos_por_pliego or 0)
        mt = Decimal(producto.merma_tinta or 0)
        if gp > 0 and producto.tinta_insumo_id:
            # Si ya calculamos pliegos_necesarios arriba úsalo, si no, sin merma de papel
            if 'pliegos_necesarios' in locals():
                pliegos_for_ink = pliegos_necesarios
            else:
                up = int(producto.unidades_por_pliego or 0)
                if up > 0:
                    pliegos_for_ink = Decimal(math.ceil(Decimal(Decimal(cantidad) / Decimal(up))))
                else:
                    pliegos_for_ink = Decimal(0)
            if pliegos_for_ink > 0:
                gramos = (pliegos_for_ink * gp) * (Decimal(1) + mt)
                req[producto.tinta_insumo_id] += gramos
    except Exception:
        pass

    return dict(req)


def calcular_consumo_pedido(pedido) -> dict:
    """Calcula consumo para un Pedido (único producto/cantidad en este proyecto)."""
    from productos.models import ProductoInsumo
    from decimal import Decimal
    req = defaultdict(Decimal)
    if not pedido or not pedido.producto or not pedido.cantidad:
        return req
    for r in ProductoInsumo.objects.filter(producto=pedido.producto).only("insumo_id", "cantidad_por_unidad"):
        req[r.insumo_id] += Decimal(r.cantidad_por_unidad) * Decimal(pedido.cantidad)
    # Puedes agregar aquí lógica adicional si necesitas fórmulas específicas
    return dict(req)


def reservar_insumos_para_pedido(pedido):
    from insumos.models import Insumo
    from pedidos.models import OrdenProduccion
    from pedidos.strategies import seleccionar_estrategia
    estrategia = seleccionar_estrategia(pedido.producto)
    consumos = estrategia.consumo_por_insumo(pedido)
    for insumo_id, cantidad in consumos:
        insumo = Insumo.objects.select_for_update().get(id=insumo_id)
        if insumo.stock < cantidad:
            raise ValueError(f"Stock insuficiente para {insumo.nombre}")
        insumo.stock -= cantidad
        insumo.save()
    OrdenProduccion.objects.get_or_create(pedido=pedido)


def verificar_stock_consumo(consumo: dict) -> tuple[bool, dict]:
    """Verifica stock disponible para un dict de consumo {insumo_id: requerido}.
    Retorna (ok, faltantes: {insumo_id: faltan}).
    """
    if not consumo:
        return True, {}
    from insumos.models import Insumo

    ids = list(consumo.keys())
    stocks = {i.idInsumo: Decimal(i.stock) for i in Insumo.objects.filter(idInsumo__in=ids)}
    faltantes = {}
    for iid, req in consumo.items():
        disp = Decimal(stocks.get(iid, 0))
        req_dec = Decimal(req)
        if disp < req_dec:
            faltantes[iid] = float(req_dec - disp)
    return (len(faltantes) == 0), faltantes
