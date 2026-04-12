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
        'cobertura':         float(params.Ct),
        'desperdicio':       float(params.M),
        'paginas_totales':   int(params.C * params.F * params.Formas),
        'paginas_por_plancha': int(params.C),
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
    """
    req = defaultdict(Decimal)
    if not producto or not cantidad:
        return dict(req)

    try:
        receta = producto.receta_dinamica
        if receta and receta.activo:
            return receta.calcular(cantidad)
    except Exception:
        pass

    from productos.models import ProductoInsumo
    for r in ProductoInsumo.objects.filter(producto=producto):
        if r.es_costo_fijo:
            req[r.insumo_id] += Decimal(r.cantidad_por_unidad)
        else:
            req[r.insumo_id] += Decimal(r.cantidad_por_unidad) * Decimal(cantidad)

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
    from django.db import transaction
    import json

    consumos = calcular_consumo_pedido(pedido)
    with transaction.atomic():
        for insumo_id, cantidad in consumos.items():
            insumo = Insumo.objects.select_for_update().get(idInsumo=insumo_id)
            if insumo.stock < cantidad:
                raise ValueError(f"Stock insuficiente para {insumo.nombre}: "
                                 f"disponible={insumo.stock}, requerido={cantidad}")
            stock_anterior = insumo.stock
            insumo.stock -= int(cantidad)
            insumo.save()

            AuditEntry.objects.create(
                app_label='insumos',
                model='Insumo',
                object_id=str(insumo.idInsumo),
                object_repr=str(insumo),
                action=AuditEntry.ACTION_UPDATE,
                changes=json.dumps({
                    'stock': {'before': stock_anterior, 'after': int(insumo.stock)}
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


def devolver_insumos_para_pedido(pedido):
    """Revierte el descuento de stock. Se llama cuando se cancela un pedido En Proceso."""
    from insumos.models import Insumo
    from pedidos.models import OrdenProduccion
    from auditoria.models import AuditEntry
    import json

    consumos = calcular_consumo_pedido(pedido)
    for insumo_id, cantidad in consumos.items():
        try:
            insumo = Insumo.objects.select_for_update().get(idInsumo=insumo_id)
        except Insumo.DoesNotExist:
            continue
        stock_anterior = insumo.stock
        insumo.stock += int(cantidad)
        insumo.save(update_fields=['stock', 'updated_at'])

        AuditEntry.objects.create(
            app_label='insumos',
            model='Insumo',
            object_id=str(insumo.idInsumo),
            object_repr=str(insumo),
            action=AuditEntry.ACTION_UPDATE,
            changes=json.dumps({'stock': {'before': stock_anterior, 'after': int(insumo.stock)}}),
            extra=json.dumps({
                'category': 'stock-movement',
                'motivo': f'Devolución por cancelación de Pedido #{pedido.pk}',
                'pedido_id': pedido.pk,
                'cantidad_devuelta': int(cantidad),
                'before': stock_anterior,
                'after': int(insumo.stock),
            }),
        )

    try:
        op = OrdenProduccion.objects.get(pedido=pedido)
        op.estado = 'cancelada'
        op.save(update_fields=['estado'])
    except OrdenProduccion.DoesNotExist:
        pass


def verificar_stock_consumo(consumo: dict) -> tuple[bool, dict]:
    """Verifica stock disponible para un dict de consumo {insumo_id: requerido}."""
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
    """Aplica descuento de oferta al pedido nuevo si existe."""
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
    """Al cancelar un pedido, ajusta el score del cliente."""
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
    """Marca la oferta como aplicada y guarda el id del pedido en sus parametros."""
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
    Canales: email + WhatsApp (si tiene número) + portal interno.
    """
    import logging
    log = logging.getLogger(__name__)

    try:
        from core.notifications.engine import enviar_notificacion
        from django.template.loader import render_to_string

        cliente = pedido.cliente
        lineas  = pedido.lineas.select_related('producto').all()

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

        try:
            html_body = render_to_string('pedidos/email_entrega.html', {
                'pedido': pedido, 'cliente': cliente, 'lineas': lineas,
            })
        except Exception:
            html_body = None

        meta = {'pedido_id': pedido.pk, 'cliente_id': cliente.pk}

        if cliente.email:
            resultado = enviar_notificacion(
                destinatario=cliente.email, mensaje=texto_plano,
                canal='email', asunto=asunto, html=html_body, metadata=meta,
            )
            if not resultado.get('ok'):
                log.warning('notificar_entrega: email falló para pedido #%s: %s',
                            pedido.pk, resultado.get('error'))

        numero_wa = cliente.numero_whatsapp
        if numero_wa:
            texto_wa = (
                f"✅ *Imprenta Tucán* — Tu pedido N° {pedido.pk} fue entregado.\n"
                f"Productos: {productos_str}\n"
                f"Total: ${pedido.monto_total:,.2f}\n"
                f"¡Gracias por tu confianza! 🎉"
            )
            resultado_wa = enviar_notificacion(
                destinatario=numero_wa, mensaje=texto_wa,
                canal='whatsapp', asunto=asunto, metadata=meta,
            )
            if not resultado_wa.get('ok'):
                log.warning('notificar_entrega: WhatsApp falló para pedido #%s: %s',
                            pedido.pk, resultado_wa.get('error'))

        enviar_notificacion(
            destinatario=str(cliente.pk),
            mensaje=f'Pedido #{pedido.pk} de {cliente.nombre} {cliente.apellido} entregado.',
            canal='portal', asunto='Entrega de pedido', metadata=meta,
        )

    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception(
            'notificar_entrega_pedido: error inesperado en pedido #%s: %s', pedido.pk, exc
        )


# ── Facturación ───────────────────────────────────────────────────────────────

def crear_factura_para_pedido(pedido) -> 'Factura':
    """Crea Factura C para un pedido Entregado y envía PDF al cliente."""
    import logging
    log = logging.getLogger(__name__)
    from .models import Factura

    existing = Factura.objects.filter(pedido=pedido).first()
    if existing:
        return existing

    numero = Factura.proximo_numero()
    factura = Factura.objects.create(
        pedido=pedido, numero=numero, monto_total=pedido.monto_total,
    )
    log.info('Factura C %s emitida para pedido #%s', numero, pedido.pk)
    _enviar_factura_por_email(factura)
    return factura


def _enviar_factura_por_email(factura) -> None:
    """Envía la Factura C como PDF adjunto al email del cliente."""
    import logging
    log = logging.getLogger(__name__)

    cliente = factura.pedido.cliente
    if not cliente.email:
        log.info('_enviar_factura_por_email: cliente #%s sin email, se omite envío', cliente.pk)
        return

    try:
        from django.core.mail import EmailMessage
        from django.conf import settings

        pdf_bytes = generar_pdf_factura(factura)
        asunto = f'Factura C {factura.numero} — Pedido #{factura.pedido.pk} — Imprenta Tucán'
        cuerpo = (
            f'Hola {cliente.nombre},\n\n'
            f'Adjuntamos la Factura C correspondiente a tu pedido N° {factura.pedido.pk}.\n\n'
            f'Número de factura: {factura.numero}\n'
            f'Fecha de emisión: {factura.fecha_emision.strftime("%d/%m/%Y")}\n'
            f'Importe total: ${factura.monto_total:,.2f}\n\n'
            f'El presente comprobante no genera crédito fiscal de IVA.\n\n'
            f'Ante cualquier consulta, no dudes en contactarnos.\n'
            f'— Imprenta Tucán'
        )
        email = EmailMessage(
            subject=asunto, body=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL, to=[cliente.email],
        )
        email.attach(
            filename=f'factura_c_{factura.numero}.pdf',
            content=pdf_bytes, mimetype='application/pdf',
        )
        email.send(fail_silently=False)
        log.info('Factura C %s enviada por email a %s', factura.numero, cliente.email)

    except Exception:
        log.exception(
            '_enviar_factura_por_email: no se pudo enviar factura %s a %s',
            factura.numero, cliente.email,
        )


def generar_pdf_factura(factura) -> bytes:
    """
    Genera el PDF de Factura C siguiendo el formato estándar AFIP para monotributistas.

    Layout (fiel al modelo físico de talonario):
      - Encabezado: [datos empresa | C en recuadro | FACTURA / N° / fecha DIA|MES|AÑO]
      - Sección receptor tipo formulario (Señor/es, Domicilio, Localidad, IVA, condición venta)
      - Tabla detalle: CANTIDAD | DESCRIPCION | PRECIO UNITARIO | IMPORTE
      - Pie: TOTAL $ destacado + leyenda + CAI + fecha vencimiento
    """
    import io
    import os
    from decimal import Decimal
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image,
    )
    from reportlab.lib.units import cm

    pedido  = factura.pedido
    cliente = pedido.cliente
    lineas  = pedido.lineas.select_related('producto').all()

    # ── Datos de la empresa ───────────────────────────────────────────────────
    try:
        from configuracion.models import Parametro
        emp = {
            'nombre':    Parametro.get('EMPRESA_NOMBRE',             'Imprenta Tucán'),
            'razon':     Parametro.get('EMPRESA_RAZON_SOCIAL',       ''),
            'domicilio': Parametro.get('EMPRESA_DOMICILIO',          ''),
            'telefono':  Parametro.get('EMPRESA_TELEFONO',           ''),
            'cuit':      Parametro.get('EMPRESA_CUIT',               ''),
            'ib':        Parametro.get('EMPRESA_INGRESOS_BRUTOS',    ''),
            'inicio':    Parametro.get('EMPRESA_INICIO_ACTIVIDADES', ''),
            'cond_iva':  Parametro.get('EMPRESA_CONDICION_IVA',      'RESPONSABLE MONOTRIBUTO'),
        }
    except Exception:
        emp = {
            'nombre': 'Imprenta Tucán', 'razon': '', 'domicilio': '',
            'telefono': '', 'cuit': '', 'ib': '', 'inicio': '',
            'cond_iva': 'RESPONSABLE MONOTRIBUTO',
        }

    # ── Número de comprobante ─────────────────────────────────────────────────
    # Nuevo formato: XXXX-XXXXXXXX (2 partes numéricas)
    # Viejo formato: F-YYYY-NNNN  → mostrar completo
    partes = factura.numero.split('-')
    if len(partes) == 2 and partes[0].isdigit() and partes[1].isdigit():
        pv  = partes[0]
        num = partes[1]
    else:
        pv  = '0001'
        num = factura.numero

    fecha_e = factura.fecha_emision
    dia_s   = fecha_e.strftime('%d')
    mes_s   = fecha_e.strftime('%m')
    anio_s  = fecha_e.strftime('%Y')

    # ── Condición IVA del receptor ────────────────────────────────────────────
    _tier_iva = {
        'nuevo':       'Consumidor Final',
        'estandar':    'Consumidor Final',
        'estrategico': 'Resp. Inscripto',
        'premium':     'Resp. Inscripto',
    }
    tier = (getattr(cliente, 'tipo_cliente', '') or '').lower()
    cond_iva_rec = _tier_iva.get(tier, 'Consumidor Final')

    nombre_rec = f'{cliente.nombre} {cliente.apellido}'
    if getattr(cliente, 'razon_social', None):
        nombre_rec += f' / {cliente.razon_social}'
    cuit_rec = getattr(cliente, 'cuit', '') or '—'
    dom_rec  = (getattr(cliente, 'direccion', '')
                or getattr(cliente, 'domicilio', '') or '')
    tel_rec  = getattr(cliente, 'telefono', '') or ''
    loc_rec  = (getattr(cliente, 'ciudad', None) and str(cliente.ciudad)) or ''

    # ── Documento ─────────────────────────────────────────────────────────────
    buf    = io.BytesIO()
    PW, PH = A4
    M      = 1.5 * cm                     # margen
    W      = PW - 2 * M                   # ancho útil ≈ 17.7 cm
    doc    = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=M, rightMargin=M,
        topMargin=M, bottomMargin=M,
    )

    # ── Estilos ───────────────────────────────────────────────────────────────
    BLK  = colors.black
    GRY  = colors.HexColor('#888888')
    LGY  = colors.HexColor('#dddddd')
    DGRY = colors.HexColor('#333333')

    def st(name, size=8, bold=False, align=TA_LEFT, color=BLK, leading=None):
        return ParagraphStyle(
            name,
            fontSize=size,
            fontName='Helvetica-Bold' if bold else 'Helvetica',
            alignment=align,
            textColor=color,
            leading=leading or size + 2,
        )

    def cell(text, size=8, bold=False, align=TA_LEFT, color=BLK):
        return Paragraph(str(text), st(f's{id(text)}', size, bold, align, color))

    def money(val):
        try:
            return f'$ {Decimal(str(val)):,.2f}'
        except Exception:
            return str(val)

    story = []

    # =========================================================================
    # 1. ENCABEZADO
    #    Columnas: [empresa (izq) | C-box (centro) | factura+fecha (der)]
    # =========================================================================
    col_emp  = W * 0.50
    col_c    = W * 0.12
    col_fac  = W - col_emp - col_c

    # — Logo de la empresa —
    _logo_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'static', 'img', 'Logo Tucan_Mesa de trabajo 1.png',
    )
    if os.path.exists(_logo_path):
        _logo_img = Image(_logo_path)
        _max_w = 3.5 * cm
        _max_h = 1.8 * cm
        _iw = _logo_img.imageWidth or 1
        _ih = _logo_img.imageHeight or 1
        _scale = min(_max_w / _iw, _max_h / _ih)
        _logo_img.drawWidth  = _iw * _scale
        _logo_img.drawHeight = _ih * _scale
        _logo_img.hAlign = 'LEFT'
        _logo_cell = _logo_img
    else:
        _logo_cell = cell(emp['nombre'], size=13, bold=True)

    # — Empresa (izquierda) —
    _emp_rows = [
        [_logo_cell],
        [cell(emp['nombre'], size=10, bold=True)],
        [cell(f"{emp['domicilio']}  {emp['telefono']}".strip(' '), size=8)],
        [cell(emp['cond_iva'].upper(), size=7, bold=True)],
    ]
    if emp['razon']:
        _emp_rows.insert(2, [cell(emp['razon'], size=8, color=DGRY)])

    emp_content = Table(
        _emp_rows,
        colWidths=[col_emp - 0.3 * cm],
    )
    emp_content.setStyle(TableStyle([
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 3),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    # — Letra C (centro): celda simple, el recuadro se dibuja en el header exterior —
    c_cell = cell('C', size=32, bold=True, align=TA_CENTER)

    # — FACTURA + número + fecha (derecha) —
    # Fecha en 3 celdas: DIA | MES | AÑO
    fecha_tabla = Table(
        [
            [cell('DIA', size=6, align=TA_CENTER, color=GRY),
             cell('MES', size=6, align=TA_CENTER, color=GRY),
             cell('AÑO', size=6, align=TA_CENTER, color=GRY)],
            [cell(dia_s,  size=8, bold=True, align=TA_CENTER),
             cell(mes_s,  size=8, bold=True, align=TA_CENTER),
             cell(anio_s, size=8, bold=True, align=TA_CENTER)],
        ],
        colWidths=[1.1 * cm, 1.1 * cm, 1.6 * cm],
    )
    fecha_tabla.setStyle(TableStyle([
        ('BOX',           (0, 0), (-1, -1), 0.5, BLK),
        ('INNERGRID',     (0, 0), (-1, -1), 0.25, LGY),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING',    (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))

    fac_right = Table(
        [
            [cell('FACTURA', size=14, bold=True, align=TA_CENTER)],
            [cell(f'N° {pv}-{num}', size=9, bold=True, align=TA_CENTER)],
            [fecha_tabla],
            [cell(f'CUIT: {emp["cuit"]}', size=7)],
            [cell(f'Ing. Brutos: {emp["ib"] or emp["cuit"]}', size=7)],
            [cell(f'Inicio Act.: {emp["inicio"]}', size=7)],
        ],
        colWidths=[col_fac - 0.3 * cm],
    )
    fac_right.setStyle(TableStyle([
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    header = Table(
        [[emp_content, c_cell, fac_right]],
        colWidths=[col_emp, col_c, col_fac],
    )
    header.setStyle(TableStyle([
        # Borde exterior de todo el encabezado
        ('BOX',           (0, 0), (-1, -1), 1,   BLK),
        # Recuadro de la columna "C" (ocupa toda la altura del header automáticamente)
        ('BOX',           (1, 0), (1, 0),   1.5, BLK),
        ('ALIGN',         (1, 0), (1, 0),   'CENTER'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(header)
    story.append(Spacer(1, 0.25 * cm))

    # =========================================================================
    # 2. DATOS DEL RECEPTOR — estilo formulario con líneas punteadas
    # =========================================================================
    LINE = colors.HexColor('#aaaaaa')

    def form_row(*pairs, col_widths=None):
        """Genera una fila de formulario: [label | valor | label | valor ...]"""
        cells = []
        for label, value in pairs:
            cells.append(cell(label, size=7, color=GRY))
            cells.append(cell(value, size=8))
        t = Table([cells], colWidths=col_widths or [W / (len(pairs) * 2)] * (len(pairs) * 2))
        t.setStyle(TableStyle([
            ('TOPPADDING',    (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('LINEBELOW',     (1, 0), (1, 0),   0.5, LINE),
            ('LINEBELOW',     (3, 0), (3, 0),   0.5, LINE) if len(pairs) > 1 else ('NOP', (0,0),(0,0)),
            ('VALIGN',        (0, 0), (-1, -1), 'BOTTOM'),
        ]))
        return t

    story.append(form_row(
        ('Señor/es:', nombre_rec),
        ('Teléfono:', tel_rec),
        col_widths=[2 * cm, 10 * cm, 2 * cm, W - 14 * cm],
    ))
    story.append(form_row(
        ('Domicilio:', dom_rec),
        ('Localidad:', loc_rec),
        col_widths=[2 * cm, 9 * cm, 2.2 * cm, W - 13.2 * cm],
    ))

    # Fila IVA con checkboxes simulados
    def check(label, marcado=False):
        mark = '[X]' if marcado else '[ ]'
        return cell(f'{mark} {label}', size=7)

    iva_ri  = cond_iva_rec == 'Resp. Inscripto'
    iva_cf  = cond_iva_rec == 'Consumidor Final'
    iva_mon = cond_iva_rec == 'Resp. Monotributo'

    iva_row = Table(
        [[
            cell('I.V.A.:', size=7, color=GRY),
            check('Resp. Inscripto',   iva_ri),
            check('Resp. Monotributo', iva_mon),
            check('Consumidor Final',  iva_cf),
            check('No Responsable',    False),
            check('Exento',            False),
            cell('C.U.I.T. N°:', size=7, color=GRY),
            cell(cuit_rec, size=8),
        ]],
        colWidths=[1.2*cm, 2.5*cm, 2.9*cm, 2.5*cm, 2.2*cm, 1.3*cm, 1.8*cm, W-14.4*cm],
    )
    iva_row.setStyle(TableStyle([
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 2),
        ('LINEBELOW',     (7, 0), (7, 0),   0.5, LINE),
        ('VALIGN',        (0, 0), (-1, -1), 'BOTTOM'),
        ('BOX',           (0, 0), (-1, -1), 0.5, LINE),
    ]))
    story.append(iva_row)

    # Condiciones de venta
    venta_row = Table(
        [[
            cell('Condiciones de venta:', size=7, color=GRY),
            check('Contado',          True),
            check('Cuenta Corriente', False),
            cell('Remito N°:', size=7, color=GRY),
            cell('', size=8),
        ]],
        colWidths=[3.8*cm, 1.9*cm, 3.5*cm, 2.2*cm, W-11.4*cm],
    )
    venta_row.setStyle(TableStyle([
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 2),
        ('LINEBELOW',     (4, 0), (4, 0),   0.5, LINE),
        ('VALIGN',        (0, 0), (-1, -1), 'BOTTOM'),
        ('BOX',           (0, 0), (-1, -1), 0.5, LINE),
    ]))
    story.append(venta_row)
    story.append(Spacer(1, 0.2 * cm))

    # =========================================================================
    # 3. TABLA DETALLE — CANTIDAD | DESCRIPCION | PRECIO UNITARIO | IMPORTE
    # =========================================================================
    cw_det = [2.5 * cm, W - 8.5 * cm, 3 * cm, 3 * cm]

    th_style = dict(size=8, bold=True, align=TA_CENTER, color=colors.white)
    det_data = [[
        cell('CANTIDAD',       **th_style),
        cell('DESCRIPCION',    **th_style),
        cell('PRECIO UNITARIO',**th_style),
        cell('IMPORTE',        **th_style),
    ]]

    subtotal = Decimal('0')
    for l in lineas:
        precio  = l.precio_unitario or Decimal('0')
        importe = precio * l.cantidad
        subtotal += importe
        desc = l.producto.nombreProducto
        if l.especificaciones:
            desc += f' ({l.especificaciones})'
        det_data.append([
            cell(str(l.cantidad), align=TA_CENTER),
            cell(desc),
            cell(money(precio),   align=TA_RIGHT),
            cell(money(importe),  align=TA_RIGHT),
        ])

    # Rellenar con filas vacías para llegar a mínimo 8 líneas (aspecto de talonario)
    MIN_ROWS = 8
    while len(det_data) < MIN_ROWS + 1:
        det_data.append([cell(''), cell(''), cell(''), cell('')])

    n = len(det_data)
    row_bgs = [colors.HexColor('#1e3a5f')] + [
        colors.white if i % 2 == 1 else colors.HexColor('#f9f9f9')
        for i in range(1, n)
    ]

    det_table = Table(det_data, colWidths=cw_det, repeatRows=1)
    det_table.setStyle(TableStyle([
        ('ROWBACKGROUNDS',  (0, 0), (-1, -1), row_bgs),
        ('TEXTCOLOR',       (0, 0), (-1, 0),  colors.white),
        ('FONTSIZE',        (0, 0), (-1, -1), 8),
        ('TOPPADDING',      (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',   (0, 0), (-1, -1), 4),
        ('LEFTPADDING',     (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',    (0, 0), (-1, -1), 5),
        ('GRID',            (0, 0), (-1, -1), 0.3, LGY),
        ('LINEBELOW',       (0, 0), (-1, 0),  1,   colors.HexColor('#1e3a5f')),
        ('VALIGN',          (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',           (0, 0), (0, -1),  'CENTER'),
        ('ALIGN',           (2, 0), (3, -1),  'RIGHT'),
    ]))
    story.append(det_table)
    story.append(Spacer(1, 0.15 * cm))

    # =========================================================================
    # 4. TOTALES + LEYENDA + CAI
    # =========================================================================
    descuento = Decimal(str(pedido.descuento or 0))
    monto_dto = subtotal * descuento / Decimal('100')

    # Fila de descuento (si aplica)
    subtotales_rows = []
    subtotales_rows.append([cell('Subtotal', size=8, align=TA_RIGHT),
                             cell(money(subtotal), size=8, align=TA_RIGHT)])
    if descuento:
        subtotales_rows.append([
            cell(f'Descuento ({descuento:.0f}%)', size=8, align=TA_RIGHT),
            cell(f'- {money(monto_dto)}', size=8, align=TA_RIGHT),
        ])

    sub_table = Table(subtotales_rows, colWidths=[4 * cm, 3.5 * cm], hAlign='RIGHT')
    sub_table.setStyle(TableStyle([
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('LINEBELOW',     (0, -1), (-1, -1), 0.5, LGY),
    ]))
    story.append(sub_table)

    # TOTAL $ box destacado (igual que el modelo físico)
    total_table = Table(
        [[
            cell('TOTAL $', size=11, bold=True, align=TA_RIGHT, color=colors.white),
            cell(money(pedido.monto_total), size=11, bold=True, align=TA_RIGHT, color=colors.white),
        ]],
        colWidths=[4 * cm, 3.5 * cm],
        hAlign='RIGHT',
    )
    total_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor('#1e3a5f')),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('BOX',           (0, 0), (-1, -1), 1, colors.HexColor('#1e3a5f')),
    ]))
    story.append(total_table)

    # Leyenda + separador
    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=LGY))
    story.append(Spacer(1, 0.15 * cm))

    st_ly = ParagraphStyle('LY', fontSize=7, textColor=GRY,
                            alignment=TA_CENTER, leading=9)
    story.append(Paragraph(
        'El presente comprobante no genera crédito fiscal de IVA.  '
        'ORIGINAL BLANCO / DUPLICADO COLOR',
        st_ly,
    ))
    story.append(Spacer(1, 0.15 * cm))

    # CAI y fecha vencimiento (pie)
    cai_row = Table(
        [[
            cell(f'CUIT: {emp["cuit"]}', size=7, color=GRY),
            cell('C.A.I.: ___________________________', size=7, color=GRY, align=TA_CENTER),
            cell('Fecha vencimiento: ___/___/______', size=7, color=GRY, align=TA_RIGHT),
        ]],
        colWidths=[4 * cm, W - 8 * cm, 4 * cm],
    )
    cai_row.setStyle(TableStyle([
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
    ]))
    story.append(cai_row)
    story.append(Spacer(1, 0.1 * cm))
    story.append(Paragraph(
        f'Generado el {fecha_e.strftime("%d/%m/%Y %H:%M")}  ·  Pedido #{pedido.pk}',
        st_ly,
    ))

    doc.build(story)
    return buf.getvalue()
