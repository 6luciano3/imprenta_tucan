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
    from django.db import transaction
    import json

    consumos = calcular_consumo_pedido(pedido)
    # C-4: toda la reserva va dentro de una transacción para garantizar consistencia.
    # Si cualquier insumo falla, el stock de los anteriores no se modifica.
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


def devolver_insumos_para_pedido(pedido):
    """Revierte el descuento de stock generado por reservar_insumos_para_pedido.
    Se llama cuando un pedido en estado 'En Proceso' es cancelado.
    Suma de vuelta las cantidades al stock de cada insumo y registra en auditoría.
    """
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

    # Cancelar la OrdenProduccion asociada si existe
    try:
        op = OrdenProduccion.objects.get(pedido=pedido)
        op.estado = 'cancelada'
        op.save(update_fields=['estado'])
    except OrdenProduccion.DoesNotExist:
        pass


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


# ─── Facturación ──────────────────────────────────────────────────────────────

def crear_factura_para_pedido(pedido) -> 'Factura':
    """
    Crea el registro Factura para un pedido que acaba de pasar a Entregado
    y envía el PDF al cliente por email.
    Si ya existe una factura para ese pedido, la devuelve sin duplicar
    (no reenvía el email).
    """
    import logging
    log = logging.getLogger(__name__)
    from .models import Factura

    existing = Factura.objects.filter(pedido=pedido).first()
    if existing:
        return existing

    numero = Factura.proximo_numero()
    factura = Factura.objects.create(
        pedido=pedido,
        numero=numero,
        monto_total=pedido.monto_total,
    )
    log.info('Factura %s emitida para pedido #%s', numero, pedido.pk)

    _enviar_factura_por_email(factura)
    return factura


def _enviar_factura_por_email(factura) -> None:
    """Envía la factura como PDF adjunto al email del cliente."""
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

        asunto = f'Factura {factura.numero} — Pedido #{factura.pedido.pk} — Imprenta Tucán'

        cuerpo = (
            f'Hola {cliente.nombre},\n\n'
            f'Adjuntamos la factura correspondiente a tu pedido N° {factura.pedido.pk}.\n\n'
            f'Número de factura: {factura.numero}\n'
            f'Fecha de emisión: {factura.fecha_emision.strftime("%d/%m/%Y")}\n'
            f'Total: ${factura.monto_total:,.2f}\n\n'
            f'Ante cualquier consulta, no dudes en contactarnos.\n'
            f'— Imprenta Tucán'
        )

        email = EmailMessage(
            subject=asunto,
            body=cuerpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[cliente.email],
        )
        email.attach(
            filename=f'factura_{factura.numero}.pdf',
            content=pdf_bytes,
            mimetype='application/pdf',
        )
        email.send(fail_silently=False)
        log.info('Factura %s enviada por email a %s', factura.numero, cliente.email)

    except Exception:
        log.exception(
            '_enviar_factura_por_email: no se pudo enviar factura %s a %s',
            factura.numero, cliente.email,
        )


def generar_pdf_factura(factura) -> bytes:
    """
    Genera el PDF de la factura usando reportlab y devuelve bytes.
    """
    import io
    from decimal import Decimal
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.units import cm

    pedido = factura.pedido
    cliente = pedido.cliente
    lineas = pedido.lineas.select_related('producto').all()

    # Datos empresa
    try:
        from configuracion.models import Parametro
        empresa = {
            'nombre':    Parametro.get('EMPRESA_NOMBRE',    'Imprenta Tucán S.A.'),
            'cuit':      Parametro.get('EMPRESA_CUIT',      ''),
            'domicilio': Parametro.get('EMPRESA_DOMICILIO', ''),
            'telefono':  Parametro.get('EMPRESA_TELEFONO',  ''),
            'email':     Parametro.get('EMPRESA_EMAIL',     ''),
            'iva':       Parametro.get('EMPRESA_CONDICION_IVA', 'Responsable Inscripto'),
        }
    except Exception:
        empresa = {'nombre': 'Imprenta Tucán S.A.', 'cuit': '', 'domicilio': '',
                   'telefono': '', 'email': '', 'iva': 'Responsable Inscripto'}

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    st_normal = styles['Normal']
    st_normal.fontSize = 9
    st_h1 = ParagraphStyle('H1', fontSize=16, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=4)
    st_h2 = ParagraphStyle('H2', fontSize=11, fontName='Helvetica-Bold', spaceAfter=2)
    st_small = ParagraphStyle('Small', fontSize=8, textColor=colors.grey)
    st_right = ParagraphStyle('Right', fontSize=9, alignment=TA_RIGHT)
    st_bold = ParagraphStyle('Bold', fontSize=9, fontName='Helvetica-Bold')
    st_total = ParagraphStyle('Total', fontSize=11, fontName='Helvetica-Bold', alignment=TA_RIGHT)

    # ── Utilidades ────────────────────────────────────────────────────────────
    def money(val):
        try:
            return f'$ {Decimal(str(val)):,.2f}'
        except Exception:
            return str(val)

    story = []

    # ── Encabezado ────────────────────────────────────────────────────────────
    header_data = [
        [
            Paragraph(f'<b>{empresa["nombre"]}</b>', st_h2),
            Paragraph('<b>FACTURA</b>', st_h1),
        ],
        [
            Paragraph(
                f'CUIT: {empresa["cuit"]}<br/>'
                f'{empresa["domicilio"]}<br/>'
                f'Tel: {empresa["telefono"]}<br/>'
                f'Email: {empresa["email"]}<br/>'
                f'IVA: {empresa["iva"]}',
                st_normal,
            ),
            Table(
                [
                    ['N°:', factura.numero],
                    ['Fecha:', factura.fecha_emision.strftime('%d/%m/%Y')],
                    ['Pedido:', f'#{pedido.pk}'],
                    ['Estado:', pedido.estado.nombre],
                ],
                colWidths=[2.5*cm, 4.5*cm],
                style=TableStyle([
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                    ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.whitesmoke, colors.white]),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ]),
            ),
        ],
    ]
    header_table = Table(header_data, colWidths=[9*cm, 8*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 1), (-1, 1), 0, colors.white),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#1e40af')))
    story.append(Spacer(1, 0.3*cm))

    # ── Datos del cliente ─────────────────────────────────────────────────────
    story.append(Paragraph('DATOS DEL CLIENTE', st_h2))
    cliente_data = [
        ['Nombre / Razón Social:', f'{cliente.nombre} {cliente.apellido}' +
            (f' — {cliente.razon_social}' if getattr(cliente, 'razon_social', None) else '')],
        ['CUIT:', getattr(cliente, 'cuit', '') or '—'],
        ['Email:', cliente.email or '—'],
        ['Teléfono:', getattr(cliente, 'telefono', '') or '—'],
    ]
    cliente_table = Table(cliente_data, colWidths=[5*cm, 12*cm])
    cliente_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.whitesmoke, colors.white]),
    ]))
    story.append(cliente_table)
    story.append(Spacer(1, 0.4*cm))

    # ── Detalle de líneas ─────────────────────────────────────────────────────
    story.append(Paragraph('DETALLE', st_h2))
    col_widths = [6.5*cm, 2*cm, 3*cm, 3.5*cm, 2*cm]
    lineas_data = [['Producto', 'Cant.', 'Unitario', 'Importe', 'Espec.']]
    subtotal = Decimal('0')
    for l in lineas:
        precio = l.precio_unitario or Decimal('0')
        importe = precio * l.cantidad
        subtotal += importe
        lineas_data.append([
            l.producto.nombreProducto,
            str(l.cantidad),
            money(precio),
            money(importe),
            l.especificaciones or '—',
        ])

    lineas_table = Table(lineas_data, colWidths=col_widths, repeatRows=1)
    lineas_table.setStyle(TableStyle([
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (4, 0), (4, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#1e40af')),
    ]))
    story.append(lineas_table)
    story.append(Spacer(1, 0.3*cm))

    # ── Totales ───────────────────────────────────────────────────────────────
    descuento = Decimal(str(pedido.descuento or 0))
    monto_descuento = subtotal * descuento / Decimal('100')
    subtotal_con_dto = subtotal - monto_descuento

    try:
        from configuracion.models import Parametro as _P
        iva_rate = Decimal(str(_P.get('IVA_PORCENTAJE', '0.21')))
    except Exception:
        iva_rate = Decimal('0.21')

    monto_iva = subtotal_con_dto * iva_rate if pedido.aplicar_iva else Decimal('0')

    totales_rows = []
    totales_rows.append(['Subtotal', money(subtotal)])
    if descuento:
        totales_rows.append([f'Descuento ({descuento:.0f}%)', f'— {money(monto_descuento)}'])
    if pedido.aplicar_iva:
        totales_rows.append([f'IVA ({iva_rate*100:.0f}%)', money(monto_iva)])
    totales_rows.append(['TOTAL', money(pedido.monto_total)])

    totales_table = Table(totales_rows, colWidths=[4*cm, 3.5*cm], hAlign='RIGHT')
    totales_style = [
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]
    last = len(totales_rows) - 1
    totales_style += [
        ('BACKGROUND', (0, last), (-1, last), colors.HexColor('#eff6ff')),
        ('FONTNAME', (0, last), (-1, last), 'Helvetica-Bold'),
        ('FONTSIZE', (0, last), (-1, last), 11),
        ('LINEABOVE', (0, last), (-1, last), 1, colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, last), (-1, last), colors.HexColor('#1e40af')),
    ]
    totales_table.setStyle(TableStyle(totales_style))
    story.append(totales_table)

    # ── Pie ───────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.8*cm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        f'Documento generado automáticamente el {factura.fecha_emision.strftime("%d/%m/%Y %H:%M")}. '
        f'Pedido #{pedido.pk} — Fecha de entrega: {pedido.fecha_entrega.strftime("%d/%m/%Y") if pedido.fecha_entrega else "—"}.',
        st_small,
    ))

    doc.build(story)
    return buf.getvalue()
