from decimal import Decimal
from collections import defaultdict
import math


def _build_formula_variables(params, cantidad: int) -> dict:
    """
    Construye el diccionario de variables para safe_eval a partir de
    ParametroProducto y la cantidad del trabajo (tirada).
    Cubre los nombres de variable usados en las fórmulas registradas.
    """
    return {
        'tirada':            float(cantidad),
        'cantidad':          float(cantidad),
        'ancho_cm':          float(params.ancho_pliego_cm),
        'alto_cm':           float(params.alto_pliego_cm),
        'cobertura':         float(params.Ct),          # g/m2 por color
        'desperdicio':       float(params.M),            # ej: 0.05
        'paginas_totales':   int(params.C * params.F * params.Formas),
        'paginas_por_plancha': int(params.C),            # 1 plancha por color
        # Consumibles por horas: sin datos de producción, se usa 1 como default
        'horas':             1,
        'consumo_por_hora':  1,
    }


def calcular_con_formula(producto, cantidad: int) -> dict:
    """
    Evalúa producto.formula usando los ParametroProducto del producto.
    Retorna {insumo_id: Decimal(resultado)} o {} si no aplica.
    """
    try:
        formula = producto.formula
        if not formula or not formula.activo:
            return {}
        params = producto.parametros_tecnicos
    except Exception:
        return {}

    variables = _build_formula_variables(params, cantidad)
    try:
        from configuracion.utils.safe_eval import safe_eval
        resultado = Decimal(str(safe_eval(formula.expresion, variables)))
        if resultado > 0:
            return {formula.insumo_id: resultado}
    except Exception:
        return {}
    return {}


def calcular_consumo_producto(producto, cantidad: int) -> dict:
    """
    Calcula consumo de insumos para un producto y una cantidad de trabajo.

    Prioridad:
      1. RecetaDinamica (si existe y está activa)
      2. BOM estático (ProductoInsumo)
      3. Fórmula dinámica (producto.formula + ParametroProducto)
         — complementa el BOM: solo agrega insumos que el BOM no incluye.
    """
    req = defaultdict(Decimal)
    if not producto or not cantidad:
        return dict(req)

    # 1. RecetaDinamica
    try:
        receta = producto.receta_dinamica
        if receta and receta.activo:
            return receta.calcular(cantidad)
    except Exception:
        pass

    # 2. BOM estático
    from productos.models import ProductoInsumo
    for r in ProductoInsumo.objects.filter(producto=producto):
        if r.es_costo_fijo:
            req[r.insumo_id] += Decimal(r.cantidad_por_unidad)
        else:
            req[r.insumo_id] += Decimal(r.cantidad_por_unidad) * Decimal(cantidad)

    # 3. Fórmula dinámica — complementa insumos no cubiertos por el BOM
    for insumo_id, qty in calcular_con_formula(producto, cantidad).items():
        if insumo_id not in req:
            req[insumo_id] = qty

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


def notificar_entrega_pedido(pedido):
    """
    Envía notificación multicanal al cliente cuando su pedido pasa a "Entregado".
    Canales: email (siempre) + WhatsApp (si tiene número) + portal interno.
    Nunca lanza excepción — los errores se registran en el log y en AutomationLog.
    """
    import logging
    log = logging.getLogger(__name__)

    try:
        from core.notifications.engine import enviar_notificacion
        from django.template.loader import render_to_string

        cliente = pedido.cliente
        lineas  = pedido.lineas.select_related('producto').all()

        # ── Textos ────────────────────────────────────────────────────────────
        productos_str = ', '.join(
            f"{l.producto.nombreProducto} (x{l.cantidad})" for l in lineas
        ) or 'Ver detalle en nuestras oficinas'

        asunto = f'Tu pedido #{pedido.pk} fue entregado — Imprenta Tucán'

        texto_plano = (
            f"Hola {cliente.nombre},\n\n"
            f"Te informamos que tu pedido N° {pedido.pk} ha sido entregado.\n\n"
            f"Productos: {productos_str}\n"
            f"Total: ${pedido.monto_total:,.2f}\n"
            f"Fecha de entrega: {pedido.fecha_entrega}\n\n"
            f"Gracias por confiar en Imprenta Tucán.\n"
            f"Ante cualquier consulta, no dudes en contactarnos."
        )

        # ── HTML email ────────────────────────────────────────────────────────
        try:
            html_body = render_to_string('pedidos/email_entrega.html', {
                'pedido':   pedido,
                'cliente':  cliente,
                'lineas':   lineas,
            })
        except Exception:
            html_body = None   # fallback a texto plano si el template falla

        meta = {'pedido_id': pedido.pk, 'cliente_id': cliente.pk}

        # ── Email ─────────────────────────────────────────────────────────────
        if cliente.email:
            resultado = enviar_notificacion(
                destinatario=cliente.email,
                mensaje=texto_plano,
                canal='email',
                asunto=asunto,
                html=html_body,
                metadata=meta,
            )
            if not resultado.get('ok'):
                log.warning('notificar_entrega: email falló para pedido #%s: %s',
                            pedido.pk, resultado.get('error'))

        # ── WhatsApp ──────────────────────────────────────────────────────────
        numero_wa = cliente.numero_whatsapp
        if numero_wa:
            texto_wa = (
                f"✅ *Imprenta Tucán* — Tu pedido N° {pedido.pk} fue entregado.\n"
                f"Productos: {productos_str}\n"
                f"Total: ${pedido.monto_total:,.2f}\n"
                f"¡Gracias por tu confianza! 🎉"
            )
            resultado_wa = enviar_notificacion(
                destinatario=numero_wa,
                mensaje=texto_wa,
                canal='whatsapp',
                asunto=asunto,
                metadata=meta,
            )
            if not resultado_wa.get('ok'):
                log.warning('notificar_entrega: WhatsApp falló para pedido #%s: %s',
                            pedido.pk, resultado_wa.get('error'))

        # ── Portal interno ────────────────────────────────────────────────────
        enviar_notificacion(
            destinatario=str(cliente.pk),
            mensaje=f'Pedido #{pedido.pk} de {cliente.nombre} {cliente.apellido} entregado.',
            canal='portal',
            asunto='Entrega de pedido',
            metadata=meta,
        )

    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception(
            'notificar_entrega_pedido: error inesperado en pedido #%s: %s', pedido.pk, exc
        )
