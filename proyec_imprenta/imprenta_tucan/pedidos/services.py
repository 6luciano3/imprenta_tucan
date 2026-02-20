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
    from configuracion.models import Formula
    from configuracion.utils.safe_eval import safe_eval
    req = defaultdict(Decimal)
    if not producto or not cantidad:
        return req

    # Si el producto tiene fórmula asociada, usarla
    if hasattr(producto, 'formula') and producto.formula:
        formula = producto.formula
        # Obtener insumo asociado a la fórmula
        insumo = getattr(formula, 'insumo', None)
        if insumo:
            # Preparar variables para la fórmula
            variables = {}
            # Variables estándar: cantidad, producto, etc.
            variables['cantidad'] = cantidad
            # Agregar variables del producto si existen
            # (ejemplo: tirada, ancho_cm, alto_cm, cobertura, desperdicio, etc.)
            for var in (formula.variables_json or {}):
                # Buscar en el producto o usar 0 si no existe
                valor = getattr(producto, var, None)
                if valor is None:
                    # Permitir buscar en un dict de parámetros si existe
                    if hasattr(producto, 'parametros') and var in producto.parametros:
                        valor = producto.parametros[var]
                    else:
                        valor = 0
                variables[var] = valor
            # Evaluar la expresión de la fórmula
            try:
                resultado = safe_eval(formula.expresion, variables)
                req[insumo.idInsumo] += Decimal(resultado)
            except Exception as e:
                # Si falla la fórmula, fallback a receta estática
                pass
            return dict(req)

    # Fallback: receta estática
    from insumos.models import Insumo
    for r in ProductoInsumo.objects.filter(producto=producto).select_related('insumo').only("insumo_id", "cantidad_por_unidad", "insumo__nombre"):
        nombre_insumo = (r.insumo.nombre or '').lower()
        # Si es una plancha, solo sumar una vez la cantidad por trabajo
        if 'plancha' in nombre_insumo:
            req[r.insumo_id] += Decimal(r.cantidad_por_unidad)
        else:
            req[r.insumo_id] += Decimal(r.cantidad_por_unidad) * Decimal(cantidad)

    # Lógica adicional de papel y tinta (legacy, si no hay fórmula)
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

    try:
        gp = Decimal(producto.gramos_por_pliego or 0)
        mt = Decimal(producto.merma_tinta or 0)
        if gp > 0 and producto.tinta_insumo_id:
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
