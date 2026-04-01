from decimal import Decimal
from collections import defaultdict
import math


def calcular_consumo_producto(producto, cantidad: int) -> dict:
    """Calcula consumo usando RecetaDinamica si existe, sino fallback a BOM estatico."""
    from decimal import Decimal
    from collections import defaultdict
    req = defaultdict(Decimal)
    if not producto or not cantidad:
        return dict(req)

    # Intentar RecetaDinamica primero
    try:
        receta = producto.receta_dinamica
        if receta and receta.activo:
            return receta.calcular(cantidad)
    except Exception:
        pass

    # Fallback: BOM estatico (ProductoInsumo)
    from productos.models import ProductoInsumo
    for r in ProductoInsumo.objects.filter(producto=producto):
        if r.es_costo_fijo:
            req[r.insumo_id] += Decimal(r.cantidad_por_unidad)
        else:
            req[r.insumo_id] += Decimal(r.cantidad_por_unidad) * Decimal(cantidad)
    return dict(req)


def calcular_consumo_pedido(pedido) -> dict:
    """Calcula consumo total para un Pedido iterando todas sus líneas (LineaPedido)."""
    req = defaultdict(Decimal)
    if not pedido:
        return dict(req)
    for linea in pedido.lineas.select_related('producto').all():
        consumo_linea = calcular_consumo_producto(linea.producto, linea.cantidad)
        for insumo_id, cantidad in consumo_linea.items():
            req[insumo_id] += Decimal(cantidad)
    return dict(req)


def reservar_insumos_para_pedido(pedido):
    from insumos.models import Insumo
    from pedidos.models import OrdenProduccion
    from auditoria.models import AuditEntry
    import json

    consumos = calcular_consumo_pedido(pedido)
    for insumo_id, cantidad in consumos.items():
        insumo = Insumo.objects.select_for_update().get(idInsumo=insumo_id)
        if insumo.stock < cantidad:
            raise ValueError(f"Stock insuficiente para {insumo.nombre}: "
                             f"disponible={insumo.stock}, requerido={cantidad}")
        stock_anterior = insumo.stock
        insumo.stock -= int(cantidad)
        insumo.save()

        # Registrar en auditoría con descripción clara
        AuditEntry.objects.create(
            app_label='insumos',
            model='Insumo',
            object_id=str(insumo.idInsumo),
            object_repr=str(insumo),
            action=AuditEntry.ACTION_UPDATE,
            changes=json.dumps({
                'stock': {
                    'before': stock_anterior,
                    'after': int(insumo.stock),
                }
            }),
            extra=json.dumps({
                'category': 'stock-movement',
                'motivo': f'Descuento automático por Pedido #{pedido.pk} → "{pedido.estado}"',
                'pedido_id': pedido.pk,
                'cantidad_descontada': int(cantidad),
                'before': stock_anterior,
                'after': int(insumo.stock),
            }),
        )

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


def aplicar_descuento_oferta(pedido):
    """
    T-05: Si el cliente tiene una oferta de descuento aceptada, aplica el porcentaje
    al monto_total del pedido. Retorna la oferta encontrada o None.
    Solo debe llamarse en pedidos nuevos (sin pk).
    """
    try:
        from automatizacion.models import OfertaPropuesta
        oferta = (
            OfertaPropuesta.objects
            .filter(cliente=pedido.cliente, tipo="descuento", estado="aceptada")
            .order_by("-creada")
            .first()
        )
        if oferta:
            porcentaje = Decimal(str(oferta.parametros.get("descuento", 10)))
            factor = (Decimal("100") - porcentaje) / Decimal("100")
            try:
                pedido.monto_total = (pedido.monto_total * factor).quantize(pedido.monto_total)
            except Exception:
                pedido.monto_total = pedido.monto_total * factor
        return oferta
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"aplicar_descuento_oferta: error para cliente {pedido.cliente_id}: {e}")
        return None


def ajustar_score_cancelacion(pedido):
    """
    T-05: Al cancelar un pedido, ajusta el score del cliente y registra en AutomationLog.
    """
    try:
        from automatizacion.models import OfertaPropuesta, AutomationLog
        from automatizacion.views import _ajustar_score_por_feedback
        oferta = OfertaPropuesta.objects.filter(
            parametros__aplicada_pedido_id=pedido.pk
        ).first()
        if oferta:
            _ajustar_score_por_feedback(pedido.cliente, "rechazar")
            AutomationLog.objects.create(
                evento="pedido_cancelado_score_ajustado",
                descripcion=f"Pedido #{pedido.pk} cancelado. Score de {pedido.cliente} ajustado.",
                datos={"pedido_id": pedido.pk, "cliente_id": pedido.cliente_id, "oferta_id": oferta.id},
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"ajustar_score_cancelacion: error en pedido {pedido.pk}: {e}")


def marcar_oferta_aplicada(pedido, oferta):
    """
    T-05: Marca la oferta como aplicada y guarda el id del pedido en sus parametros.
    """
    try:
        oferta.estado = "aplicada"
        params = oferta.parametros or {}
        params["aplicada_pedido_id"] = pedido.pk
        oferta.parametros = params
        oferta.save()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"marcar_oferta_aplicada: error para oferta {oferta.id}: {e}")
