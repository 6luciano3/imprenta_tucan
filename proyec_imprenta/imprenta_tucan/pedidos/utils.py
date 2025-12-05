from django.db import transaction
from django.db.models import Sum
from collections import defaultdict


def verificar_insumos_disponibles(producto, cantidad: int) -> bool:
    """
    Verifica disponibilidad de insumos para cumplir con la cantidad solicitada.
    Simplificación: suma el stock de insumos activos y valida que sea >= cantidad.
    En escenarios reales, debería mapear producto -> insumos requeridos (BOM).
    """
    try:
        from insumos.models import Insumo
    except Exception:
        return False

    # Si el producto tiene receta (ProductoInsumo), validar insumos específicos
    try:
        from productos.models import ProductoInsumo
        receta = list(ProductoInsumo.objects.filter(producto=producto).select_related('insumo'))
    except Exception:
        receta = []

    if receta:
        faltante = False
        for r in receta:
            requerido = float(r.cantidad_por_unidad) * float(cantidad or 0)
            if r.insumo.stock < requerido:
                faltante = True
                break
        return not faltante

    # Fallback: sin receta definida, validar sobre stock total activo
    total_stock = (
        Insumo.objects.filter(activo=True).aggregate(total=Sum("stock")).get("total") or 0
    )
    return int(total_stock) >= int(cantidad or 0)


def verificar_insumos_para_lineas(lineas: list[tuple]) -> tuple[bool, dict]:
    """
    Verifica en conjunto los insumos necesarios para múltiples líneas.
    lineas: lista de tuplas (producto, cantidad)
    Retorna (ok, faltantes_por_insumo_id)
    """
    try:
        from insumos.models import Insumo
        from productos.models import ProductoInsumo
    except Exception:
        return False, {}

    requeridos = defaultdict(float)  # insumo_id -> cantidad requerida

    hay_receta = False
    for producto, cantidad in lineas:
        if not producto or not cantidad:
            continue
        receta = list(ProductoInsumo.objects.filter(producto=producto).only('insumo_id', 'cantidad_por_unidad'))
        if receta:
            hay_receta = True
            for r in receta:
                requeridos[r.insumo_id] += float(r.cantidad_por_unidad) * float(cantidad)

    if not hay_receta:
        # Si no hay recetas en ninguna línea, mantener la validación simple por cada línea
        for producto, cantidad in lineas:
            if not verificar_insumos_disponibles(producto, cantidad):
                return False, {}
        return True, {}

    faltantes = {}
    stocks = {i.idInsumo: i.stock for i in Insumo.objects.filter(idInsumo__in=requeridos.keys())}
    for insumo_id, req in requeridos.items():
        disp = float(stocks.get(insumo_id, 0))
        if disp < req:
            faltantes[insumo_id] = req - disp
    return (len(faltantes) == 0), faltantes


def descontar_insumos_para_lineas(lineas: list[tuple]) -> None:
    """Descuenta el stock de insumos para las líneas dadas, usando receta.
    Debe ejecutarse dentro de una transacción atómica si se combina con creación de pedidos.
    """
    from insumos.models import Insumo
    from productos.models import ProductoInsumo

    requeridos = defaultdict(float)
    for producto, cantidad in lineas:
        if not producto or not cantidad:
            continue
        for r in ProductoInsumo.objects.filter(producto=producto).only('insumo_id', 'cantidad_por_unidad'):
            requeridos[r.insumo_id] += float(r.cantidad_por_unidad) * float(cantidad)

    if not requeridos:
        return

    # Lock de filas para evitar condiciones de carrera
    insumos = list(Insumo.objects.select_for_update().filter(idInsumo__in=requeridos.keys()))
    insumos_by_id = {i.idInsumo: i for i in insumos}
    for insumo_id, req in requeridos.items():
        ins = insumos_by_id.get(insumo_id)
        if not ins:
            continue
        ins.stock = int(float(ins.stock) - req)
        if ins.stock < 0:
            ins.stock = 0
        ins.save(update_fields=["stock", "updated_at"])  # updated_at existe en modelo


def _calcular_requerimientos(lineas: list[tuple]) -> dict:
    """Calcula requerimientos agregados de insumos para una lista de líneas (producto, cantidad).
    Devuelve dict {insumo_id: requerido_float}.
    """
    from productos.models import ProductoInsumo

    requeridos = defaultdict(float)
    for producto, cantidad in lineas:
        if not producto or not cantidad:
            continue
        for r in ProductoInsumo.objects.filter(producto=producto).only('insumo_id', 'cantidad_por_unidad'):
            requeridos[r.insumo_id] += float(r.cantidad_por_unidad) * float(cantidad)
    return requeridos


def verificar_insumos_para_ajuste(old_lineas: list[tuple], new_lineas: list[tuple]) -> tuple[bool, dict]:
    """Verifica sólo el ajuste neto de insumos entre estado anterior y nuevo.
    Retorna (ok, faltantes_por_insumo_id) considerando únicamente necesidades netas positivas.
    """
    from insumos.models import Insumo

    req_old = _calcular_requerimientos(old_lineas)
    req_new = _calcular_requerimientos(new_lineas)

    netos = defaultdict(float)
    insumo_ids = set(req_old.keys()) | set(req_new.keys())
    for iid in insumo_ids:
        netos[iid] = float(req_new.get(iid, 0.0)) - float(req_old.get(iid, 0.0))

    # Sólo validar los positivos (necesitamos stock adicional)
    positivos = {iid: cant for iid, cant in netos.items() if cant > 0}
    if not positivos:
        return True, {}

    stocks = {i.idInsumo: float(i.stock) for i in Insumo.objects.filter(idInsumo__in=positivos.keys())}
    faltantes = {}
    for iid, req in positivos.items():
        disp = stocks.get(iid, 0.0)
        if disp < req:
            faltantes[iid] = req - disp
    return (len(faltantes) == 0), faltantes


def ajustar_insumos_por_diferencia(old_lineas: list[tuple], new_lineas: list[tuple]) -> None:
    """Ajusta stock en base a la diferencia neta: descuenta si aumenta, repone si disminuye.
    Debe ejecutarse dentro de una transacción atómica.
    """
    from insumos.models import Insumo

    req_old = _calcular_requerimientos(old_lineas)
    req_new = _calcular_requerimientos(new_lineas)

    netos = defaultdict(float)
    insumo_ids = set(req_old.keys()) | set(req_new.keys())
    for iid in insumo_ids:
        netos[iid] = float(req_new.get(iid, 0.0)) - float(req_old.get(iid, 0.0))

    if not netos:
        return

    insumos = list(Insumo.objects.select_for_update().filter(idInsumo__in=insumo_ids))
    insumos_by_id = {i.idInsumo: i for i in insumos}

    for iid, delta in netos.items():
        ins = insumos_by_id.get(iid)
        if not ins or delta == 0:
            continue
        # delta > 0 => descontar; delta < 0 => reponer
        ins.stock = int(float(ins.stock) - delta)
        # Si reponemos, delta es negativo => resta de negativo suma
        if ins.stock < 0:
            ins.stock = 0
        ins.save(update_fields=["stock", "updated_at"])  # mantener updated_at
