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
        # Usar receta detallada por producto-insumo con cantidad_por_unidad
        receta_items = list(ProductoInsumo.objects.filter(producto=producto).only('insumo_id', 'cantidad_por_unidad', 'es_costo_fijo'))
        if receta_items:
            hay_receta = True
            for r in receta_items:
                if r.es_costo_fijo:
                    # Costo fijo: la cantidad es por trabajo, no se multiplica por los ejemplares
                    requeridos[r.insumo_id] += float(r.cantidad_por_unidad)
                else:
                    requeridos[r.insumo_id] += float(r.cantidad_por_unidad) * float(cantidad)

    if not hay_receta:
        # Si no hay recetas en ninguna línea, mantener la validación simple por cada línea
        for producto, cantidad in lineas:
            if not verificar_insumos_disponibles(producto, cantidad):
                return False, {}
        return True, {}

    faltantes = {}
    stocks = {i.idInsumo: float(i.stock) for i in Insumo.objects.filter(idInsumo__in=requeridos.keys())}
    for insumo_id, req in requeridos.items():
        disp = float(stocks.get(insumo_id, 0.0))
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
        for r in ProductoInsumo.objects.filter(producto=producto).only('insumo_id', 'cantidad_por_unidad', 'es_costo_fijo'):
            if r.es_costo_fijo:
                requeridos[r.insumo_id] += float(r.cantidad_por_unidad)
            else:
                requeridos[r.insumo_id] += float(r.cantidad_por_unidad) * float(cantidad)

    if not requeridos:
        return

    # Lock de filas para evitar condiciones de carrera
    insumos = list(Insumo.objects.select_for_update().filter(idInsumo__in=requeridos.keys()))
    insumos_by_id = {i.idInsumo: i for i in insumos}
    import logging as _log
    _logger = _log.getLogger(__name__)
    for insumo_id, req in requeridos.items():
        ins = insumos_by_id.get(insumo_id)
        if not ins:
            continue
        stock_prev = int(float(ins.stock))
        ins.stock = int(float(ins.stock) - req)
        if ins.stock < 0:
            # M-12: registrar el desvío en lugar de truncar silenciosamente
            _logger.warning(
                'descontar_insumos_para_lineas: stock negativo en insumo #%s (%s): '
                'stock_anterior=%s req=%s → truncado a 0',
                ins.idInsumo, ins.nombre, stock_prev, req,
            )
            ins.stock = 0
        ins.save(update_fields=["stock", "updated_at"])


def _calcular_requerimientos(lineas: list[tuple]) -> dict:
    """Calcula requerimientos agregados de insumos para una lista de líneas (producto, cantidad).
    Devuelve dict {insumo_id: requerido_float}.
    """
    from productos.models import ProductoInsumo

    requeridos = defaultdict(float)
    for producto, cantidad in lineas:
        if not producto or not cantidad:
            continue
        for r in ProductoInsumo.objects.filter(producto=producto).only('insumo_id', 'cantidad_por_unidad', 'es_costo_fijo'):
            if r.es_costo_fijo:
                requeridos[r.insumo_id] += float(r.cantidad_por_unidad)
            else:
                requeridos[r.insumo_id] += float(r.cantidad_por_unidad) * float(cantidad)
    return requeridos


def calcular_insumos_bajo_minimo(lineas: list[tuple]) -> list[dict]:
    """Dado un conjunto de líneas (producto, cantidad), retorna los insumos que,
    después de consumir esas cantidades, quedarán por debajo de su stock_minimo_manual.
    Solo incluye insumos con stock suficiente (no están en faltantes).
    """
    try:
        from insumos.models import Insumo
        from productos.models import ProductoInsumo
    except Exception:
        return []

    requeridos = defaultdict(float)
    for producto, cantidad in lineas:
        if not producto or not cantidad:
            continue
        for r in ProductoInsumo.objects.filter(producto=producto).only('insumo_id', 'cantidad_por_unidad', 'es_costo_fijo'):
            if r.es_costo_fijo:
                requeridos[r.insumo_id] += float(r.cantidad_por_unidad)
            else:
                requeridos[r.insumo_id] += float(r.cantidad_por_unidad) * float(cantidad)

    if not requeridos:
        return []

    resultado = []
    for ins in Insumo.objects.filter(idInsumo__in=requeridos.keys()).only(
        'idInsumo', 'codigo', 'nombre', 'stock', 'stock_minimo_manual'
    ):
        req = requeridos[ins.idInsumo]
        stock_actual = float(ins.stock)
        if stock_actual < req:
            continue  # ya detectado como faltante
        stock_tras = stock_actual - req
        minimo = float(ins.stock_minimo_manual or 0)
        if minimo > 0 and stock_tras < minimo:
            resultado.append({
                'id': ins.idInsumo,
                'codigo': ins.codigo,
                'nombre': ins.nombre,
                'stock_tras': round(stock_tras, 2),
                'stock_minimo': round(minimo, 2),
            })
    return resultado


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

    import json
    import logging
    from auditoria.models import AuditEntry
    log = logging.getLogger(__name__)

    for iid, delta in netos.items():
        ins = insumos_by_id.get(iid)
        if not ins or delta == 0:
            continue
        stock_anterior = int(float(ins.stock))
        # delta > 0 => descontar; delta < 0 => reponer
        ins.stock = int(float(ins.stock) - delta)
        if ins.stock < 0:
            # S-4 / M-12: loguear desvío en lugar de truncar silenciosamente
            log.warning(
                'ajustar_insumos_por_diferencia: stock negativo en insumo #%s (%s): '
                'stock_anterior=%s delta=%s → truncado a 0',
                ins.idInsumo, ins.nombre, stock_anterior, delta,
            )
            ins.stock = 0
        ins.save(update_fields=["stock", "updated_at"])

        # S-4: registrar en auditoría (kardex de ajustes diferenciales por modificación de pedido)
        try:
            AuditEntry.objects.create(
                app_label='insumos',
                model='Insumo',
                object_id=str(ins.idInsumo),
                object_repr=str(ins),
                action=AuditEntry.ACTION_UPDATE,
                changes=json.dumps({'stock': {'before': stock_anterior, 'after': int(ins.stock)}}),
                extra=json.dumps({
                    'category': 'stock-movement',
                    'motivo': 'Ajuste diferencial por modificación de pedido En Proceso',
                    'delta': float(delta),
                    'before': stock_anterior,
                    'after': int(ins.stock),
                }),
            )
        except Exception as exc:
            log.warning('ajustar_insumos_por_diferencia: no se pudo registrar AuditEntry para insumo #%s: %s', ins.idInsumo, exc)
