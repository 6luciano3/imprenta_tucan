"""Utilidades de generación de PDF para presupuestos."""
import io

from django.contrib.staticfiles import finders

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        Image, HRFlowable,
    )
    _RL_OK = True
except Exception:
    _RL_OK = False


def _fmt_ars(value):
    """Formatea un Decimal/float como moneda argentina: $1.234.567,89"""
    try:
        formatted = f'{float(value):,.2f}'           # 1,234,567.89
        return '$' + formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return f'${value}'


def generar_pdf_presupuesto(presupuesto, link_respuesta=''):
    """
    Genera un PDF del presupuesto con el mismo contenido que respuesta_cliente.html.
    Retorna los bytes del PDF, o None si reportlab no está disponible.
    """
    if not _RL_OK:
        return None

    detalles = presupuesto.detalles.select_related('producto').all()
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # ---------- estilos reutilizables ----------
    def ps(name, **kwargs):
        return ParagraphStyle(name, parent=styles['Normal'], **kwargs)

    normal8  = ps('n8',  fontSize=8)
    normal9  = ps('n9',  fontSize=9)
    normal10 = ps('n10', fontSize=10)
    bold10   = ps('b10', fontSize=10, fontName='Helvetica-Bold')
    bold12   = ps('b12', fontSize=12, fontName='Helvetica-Bold')
    bold14   = ps('b14', fontSize=14, fontName='Helvetica-Bold',
                  textColor=colors.HexColor('#1d4ed8'))
    white9   = ps('w9',  fontSize=9,  textColor=colors.white)
    white14  = ps('w14', fontSize=14, fontName='Helvetica-Bold', textColor=colors.white)
    label8   = ps('lbl', fontSize=8,  textColor=colors.HexColor('#6b7280'),
                  fontName='Helvetica-Bold')
    right8   = ps('r8',  fontSize=8,  alignment=TA_RIGHT)
    right8b  = ps('r8b', fontSize=8,  alignment=TA_RIGHT, fontName='Helvetica-Bold')
    right10b = ps('r10b',fontSize=10, alignment=TA_RIGHT, fontName='Helvetica-Bold',
                  textColor=colors.HexColor('#2563eb'))
    center8  = ps('c8',  fontSize=8,  alignment=TA_CENTER)
    gray8    = ps('g8',  fontSize=8,  textColor=colors.HexColor('#9ca3af'),
                  alignment=TA_CENTER)

    story = []

    # ─── CABECERA ──────────────────────────────────────────────────────────────
    logo_path = None
    for candidate in [
        'img/logo_tucan.png',
        'img/Logo Tucan_Mesa de trabajo 1.png',
        'img/logo.png',
    ]:
        found = finders.find(candidate)
        if found:
            logo_path = found
            break

    if logo_path:
        try:
            logo_cell = Image(logo_path, width=90, height=45)
        except Exception:
            logo_cell = Paragraph('🖨️ Imprenta Tucán', white14)
    else:
        logo_cell = Paragraph('&#128424; Imprenta Tucán', white14)

    header_table = Table(
        [[logo_cell, Paragraph('Presupuesto para su revisión', white9)]],
        colWidths=[130, None],
    )
    header_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor('#1e3a5f')),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('LEFTPADDING',   (0, 0), (-1, -1), 16),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 16),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    # ─── DATOS DEL PRESUPUESTO ────────────────────────────────────────────────
    fecha_str   = presupuesto.fecha.strftime('%d/%m/%Y')   if presupuesto.fecha   else '-'
    validez_str = presupuesto.validez.strftime('%d/%m/%Y') if presupuesto.validez else 'Sin fecha límite'

    info_rows = [
        [Paragraph(f'Presupuesto <font color="#1d4ed8"><b>{presupuesto.numero}</b></font>', normal12_blue(styles))],
        [Paragraph(f'Fecha: {fecha_str}  ·  Válido hasta: <b>{validez_str}</b>', normal9)],
        [Paragraph(f'Estado: <b>{presupuesto.estado}</b>', normal9)],
    ]
    info_table = Table(info_rows, colWidths=[None])
    info_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor('#eff6ff')),
        ('BOX',           (0, 0), (-1, -1), 0.5, colors.HexColor('#bfdbfe')),
        ('LEFTPADDING',   (0, 0), (-1, -1), 14),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 14),
        ('TOPPADDING',    (0, 0), (-1, 0),  10),
        ('BOTTOMPADDING', (0, -1),(-1,-1),  10),
        ('TOPPADDING',    (0, 1), (-1, -1),  3),
        ('BOTTOMPADDING', (0, 0), (-1, -2),  3),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 8))

    # ─── DATOS DEL CLIENTE ────────────────────────────────────────────────────
    cliente = presupuesto.cliente
    nombre_cliente = f'{cliente.nombre} {cliente.apellido}'.strip()

    client_rows = [
        [Paragraph('CLIENTE', label8)],
        [Paragraph(nombre_cliente, bold10)],
    ]
    if cliente.razon_social:
        client_rows.append([Paragraph(cliente.razon_social, normal9)])

    client_table = Table(client_rows, colWidths=[None])
    client_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
        ('BOX',           (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('LEFTPADDING',   (0, 0), (-1, -1), 14),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 14),
        ('TOPPADDING',    (0, 0), (-1, 0),  10),
        ('BOTTOMPADDING', (0, -1),(-1,-1),  10),
        ('TOPPADDING',    (0, 1), (-1, -1),  3),
        ('BOTTOMPADDING', (0, 0), (-1, -2),  3),
    ]))
    story.append(client_table)
    story.append(Spacer(1, 8))

    # ─── TABLA DE DETALLE ─────────────────────────────────────────────────────
    story.append(Paragraph('DETALLE', label8))
    story.append(Spacer(1, 4))

    th = [
        Paragraph('<b>Producto</b>',  ps('th1', fontSize=8, fontName='Helvetica-Bold')),
        Paragraph('<b>Cant.</b>',     ps('th2', fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER)),
        Paragraph('<b>P. Unit.</b>',  ps('th3', fontSize=8, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
        Paragraph('<b>Desc.</b>',     ps('th4', fontSize=8, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
        Paragraph('<b>Subtotal</b>',  ps('th5', fontSize=8, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
    ]
    table_rows = [th]
    for det in detalles:
        table_rows.append([
            Paragraph(det.producto.nombreProducto,        ps(f'td1_{det.pk}', fontSize=8)),
            Paragraph(str(det.cantidad),                  ps(f'td2_{det.pk}', fontSize=8, alignment=TA_CENTER)),
            Paragraph(_fmt_ars(det.precio_unitario),      ps(f'td3_{det.pk}', fontSize=8, alignment=TA_RIGHT)),
            Paragraph(f'{det.descuento}%',                ps(f'td4_{det.pk}', fontSize=8, alignment=TA_RIGHT)),
            Paragraph(_fmt_ars(det.subtotal),             ps(f'td5_{det.pk}', fontSize=8, alignment=TA_RIGHT)),
        ])

    # Fila de total
    table_rows.append([
        Paragraph('', normal8),
        Paragraph('', normal8),
        Paragraph('', normal8),
        Paragraph('<b>Total:</b>', ps('tot_lbl', fontSize=10, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
        Paragraph(f'<b>{_fmt_ars(presupuesto.total)}</b>',
                  ps('tot_val', fontSize=10, fontName='Helvetica-Bold',
                     textColor=colors.HexColor('#2563eb'), alignment=TA_RIGHT)),
    ])

    n = len(table_rows)
    det_table = Table(table_rows, colWidths=[None, 40, 72, 50, 78])
    det_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),     colors.HexColor('#f3f4f6')),
        ('GRID',          (0, 0), (-1, n - 2), 0.5, colors.HexColor('#d1d5db')),
        ('LINEABOVE',     (0, n-1),(-1, n-1),  1,   colors.HexColor('#d1d5db')),
        ('ROWBACKGROUNDS',(0, 1), (-1, n - 2), [colors.white, colors.HexColor('#f9fafb')]),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(det_table)

    # ─── OBSERVACIONES ───────────────────────────────────────────────────────
    if presupuesto.observaciones:
        story.append(Spacer(1, 8))
        obs_table = Table([
            [Paragraph('OBSERVACIONES', label8)],
            [Paragraph(presupuesto.observaciones, normal9)],
        ], colWidths=[None])
        obs_table.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
            ('BOX',           (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('LEFTPADDING',   (0, 0), (-1, -1), 14),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 14),
            ('TOPPADDING',    (0, 0), (-1, 0),  10),
            ('BOTTOMPADDING', (0, -1),(-1,-1),  10),
            ('TOPPADDING',    (0, 1), (-1, -1),  4),
        ]))
        story.append(obs_table)

    # ─── ENLACE PARA RESPONDER ────────────────────────────────────────────────
    if link_respuesta:
        story.append(Spacer(1, 12))
        link_box = Table([
            [Paragraph(
                f'<b>Para aceptar o rechazar este presupuesto, visite el siguiente enlace:</b><br/>'
                f'<a href="{link_respuesta}" color="#2563eb">{link_respuesta}</a>',
                ps('lnk', fontSize=9, textColor=colors.HexColor('#1e3a5f')),
            )],
        ], colWidths=[None])
        link_box.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor('#eff6ff')),
            ('BOX',           (0, 0), (-1, -1), 0.5, colors.HexColor('#bfdbfe')),
            ('LEFTPADDING',   (0, 0), (-1, -1), 14),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 14),
            ('TOPPADDING',    (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(link_box)

    # ─── PIE ──────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#d1d5db')))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        'Imprenta Tucán · Misiones, Argentina',
        ps('ftr', fontSize=8, textColor=colors.HexColor('#9ca3af'), alignment=TA_CENTER),
    ))

    doc.build(story)
    return buf.getvalue()


def normal12_blue(styles):
    """Devuelve un ParagraphStyle para el número de presupuesto (azul, 12pt)."""
    return ParagraphStyle(
        'pres_num',
        parent=styles['Normal'],
        fontSize=12,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1d4ed8'),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Generación de imagen PNG (para og:image y enlace directo en WhatsApp)
# ─────────────────────────────────────────────────────────────────────────────

# Paleta de colores
_C_HEADER_DARK  = (30,  58,  95)   # #1e3a5f
_C_HEADER_LIGHT = (239, 246, 255)  # #eff6ff
_C_HEADER_BORDER= (191, 219, 254)  # #bfdbfe
_C_BLUE         = (37,  99,  235)  # #2563eb
_C_GREEN        = (22,  163, 74)   # #16a34a
_C_WHITE        = (255, 255, 255)
_C_BG           = (240, 244, 248)  # #f0f4f8
_C_ROW_ALT      = (249, 250, 251)  # #f9fafb
_C_BORDER       = (209, 213, 219)  # #d1d5db
_C_TEXT_DARK    = (17,  24,  39)   # #111827
_C_TEXT_MID     = (55,  65,  81)   # #374151
_C_TEXT_LIGHT   = (156, 163, 175)  # #9ca3af
_C_TABLE_HEAD   = (243, 244, 246)  # #f3f4f6


def _pil_fonts():
    """Devuelve (font_regular, font_bold, font_small, font_title) usando PIL."""
    try:
        from PIL import ImageFont
    except ImportError:
        return None, None, None, None

    _REGULAR = [
        'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/calibri.ttf',
    ]
    _BOLD = [
        'C:/Windows/Fonts/segoeuib.ttf',
        'C:/Windows/Fonts/arialbd.ttf',
        'C:/Windows/Fonts/calibrib.ttf',
    ]

    def _try(paths, size):
        for p in paths:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
        return ImageFont.load_default()

    return (
        _try(_REGULAR, 16),   # regular
        _try(_BOLD,    18),   # bold
        _try(_REGULAR, 14),   # small
        _try(_BOLD,    22),   # title
    )


def _draw_rounded_rect(draw, x0, y0, x1, y1, radius, fill, outline=None):
    """Dibuja un rectángulo con esquinas redondeadas."""
    from PIL import ImageDraw
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline)


def _text_w(draw, text, font):
    """Ancho de texto en píxeles."""
    try:
        return draw.textlength(text, font=font)
    except Exception:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]


def generar_imagen_presupuesto(presupuesto):
    """
    Genera un PNG tipo 'tarjeta de presupuesto' listo para og:image / WhatsApp preview.
    Retorna bytes del PNG, o None si Pillow no está disponible.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    f_reg, f_bold, f_small, f_title = _pil_fonts()

    detalles = list(presupuesto.detalles.select_related('producto').all())

    W        = 800
    PAD      = 32
    INNER_W  = W - PAD * 2
    HEADER_H = 72
    INFO_H   = 88
    CLIENT_H = 68
    TH_H     = 36      # table header
    ROW_H    = 32
    TOTAL_H  = 44
    FOOTER_H = 36
    GAP      = 10

    rows_h = ROW_H * max(len(detalles), 1)
    H = HEADER_H + GAP + INFO_H + GAP + CLIENT_H + GAP + TH_H + rows_h + TOTAL_H + GAP + FOOTER_H + PAD

    img = Image.new('RGB', (W, H), _C_BG)
    draw = ImageDraw.Draw(img)

    y = 0

    # ── Cabecera azul ─────────────────────────────────────────────
    draw.rectangle([0, 0, W, HEADER_H], fill=_C_HEADER_DARK)
    draw.text((PAD, 14), 'Imprenta Tucan', font=f_title, fill=_C_WHITE)
    draw.text((PAD, 46), 'Presupuesto para su revision', font=f_small, fill=(147, 197, 253))
    y = HEADER_H + GAP

    # ── Datos del presupuesto ─────────────────────────────────────
    fecha_str   = presupuesto.fecha.strftime('%d/%m/%Y')   if presupuesto.fecha   else '-'
    validez_str = presupuesto.validez.strftime('%d/%m/%Y') if presupuesto.validez else 'Sin fecha limite'

    _draw_rounded_rect(draw, PAD, y, W - PAD, y + INFO_H, 8, _C_HEADER_LIGHT, _C_HEADER_BORDER)
    draw.text((PAD + 14, y + 10), f'Presupuesto {presupuesto.numero}', font=f_bold, fill=_C_BLUE)
    draw.text((PAD + 14, y + 38), f'Fecha: {fecha_str}   Valido hasta: {validez_str}', font=f_small, fill=_C_TEXT_MID)
    draw.text((PAD + 14, y + 60), f'Estado: {presupuesto.estado}', font=f_small, fill=_C_TEXT_MID)
    y += INFO_H + GAP

    # ── Cliente ───────────────────────────────────────────────────
    nombre_cliente = f'{presupuesto.cliente.nombre} {presupuesto.cliente.apellido}'.strip()
    _draw_rounded_rect(draw, PAD, y, W - PAD, y + CLIENT_H, 8, _C_WHITE, _C_BORDER)
    draw.text((PAD + 14, y + 8),  'CLIENTE', font=f_small, fill=_C_TEXT_LIGHT)
    draw.text((PAD + 14, y + 28), nombre_cliente, font=f_bold, fill=_C_TEXT_DARK)
    if presupuesto.cliente.razon_social:
        draw.text((PAD + 14, y + 50), presupuesto.cliente.razon_social, font=f_small, fill=_C_TEXT_MID)
    y += CLIENT_H + GAP

    # ── Tabla: encabezado ─────────────────────────────────────────
    # Columnas: Producto | Cant | P.Unit | Desc | Subtotal
    C0 = PAD
    C1 = PAD + 320   # Cant (centro)
    C2 = PAD + 420   # P. Unit (derecha)
    C3 = PAD + 560   # Desc (derecha)
    C4 = W - PAD     # Subtotal (derecha)

    draw.rectangle([PAD, y, W - PAD, y + TH_H], fill=_C_TABLE_HEAD, outline=_C_BORDER)
    draw.text((C0 + 8,  y + 9), 'Producto',  font=f_small, fill=_C_TEXT_DARK)

    for lbl, cx in [('Cant.', C1), ('P. Unit.', C2), ('Desc.', C3), ('Subtotal', C4)]:
        tw = _text_w(draw, lbl, f_small)
        x_mid = (C1 if cx == C1 else cx) - (0 if cx == C1 else int(tw))
        # right-align all numeric headers
        draw.text((cx - int(_text_w(draw, lbl, f_small)) - 6, y + 9), lbl, font=f_small, fill=_C_TEXT_DARK)

    y += TH_H

    # ── Tabla: filas ──────────────────────────────────────────────
    for i, det in enumerate(detalles):
        row_fill = _C_WHITE if i % 2 == 0 else _C_ROW_ALT
        draw.rectangle([PAD, y, W - PAD, y + ROW_H], fill=row_fill, outline=_C_BORDER)

        # Producto (truncar si es largo)
        prod_name = det.producto.nombreProducto
        max_chars = 34
        if len(prod_name) > max_chars:
            prod_name = prod_name[:max_chars - 1] + '…'
        draw.text((C0 + 8, y + 7), prod_name, font=f_small, fill=_C_TEXT_MID)

        # columnas numéricas: right-align
        for val, cx in [
            (str(det.cantidad),           C1),
            (_fmt_ars(det.precio_unitario), C2),
            (f'{det.descuento}%',          C3),
            (_fmt_ars(det.subtotal),        C4),
        ]:
            tw = int(_text_w(draw, val, f_small))
            draw.text((cx - tw - 6, y + 7), val, font=f_small, fill=_C_TEXT_MID)

        y += ROW_H

    # ── Total ─────────────────────────────────────────────────────
    draw.rectangle([PAD, y, W - PAD, y + TOTAL_H], fill=_C_TABLE_HEAD, outline=_C_BORDER)
    lbl_total = 'TOTAL:'
    tw_lbl = int(_text_w(draw, lbl_total, f_bold))
    draw.text((C3 - tw_lbl - 10, y + 12), lbl_total, font=f_bold, fill=_C_TEXT_DARK)
    total_str = _fmt_ars(presupuesto.total)
    tw_total = int(_text_w(draw, total_str, f_title))
    draw.text((C4 - tw_total - 6, y + 10), total_str, font=f_title, fill=_C_BLUE)
    y += TOTAL_H + GAP

    # ── Pie ───────────────────────────────────────────────────────
    draw.line([(PAD, y + 6), (W - PAD, y + 6)], fill=_C_BORDER, width=1)
    footer_txt = 'Imprenta Tucan  \u00b7  Misiones, Argentina'
    tw_ftr = int(_text_w(draw, footer_txt, f_small))
    draw.text(((W - tw_ftr) // 2, y + 14), footer_txt, font=f_small, fill=_C_TEXT_LIGHT)

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return buf.getvalue()
