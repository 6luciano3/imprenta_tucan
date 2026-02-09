import io
import os
import csv
from datetime import datetime

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.core.paginator import Paginator
from django.utils.encoding import smart_str
from django.urls import reverse
from django.templatetags.static import static
from django.contrib.staticfiles import finders

from insumos.models import Insumo
from proveedores.models import Proveedor
from clientes.models import Cliente
from pedidos.models import Pedido
from configuracion.services import get_page_size


try:
    # Optional dependencies for exports
    from openpyxl import Workbook
except Exception:
    Workbook = None

try:
    # ReportLab for PDF
    from reportlab.lib.pagesizes import A4, LETTER, LEGAL, landscape
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.pdfgen import canvas as rl_canvas

    class NumberedCanvas(rl_canvas.Canvas):
        """Canvas that draws 'Página x de zz' in footer and supports total page count."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            # Store the current page state, then start a new page without finalizing output yet
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            # Guarantee at least one page state (single-page documents)
            if not self._saved_page_states:
                self._saved_page_states.append(dict(self.__dict__))

            num_pages = len(self._saved_page_states)
            for idx, state in enumerate(self._saved_page_states, start=1):
                self.__dict__.update(state)
                # Footer with page number (skip when hide_footer is True)
                if not getattr(self, 'hide_footer', False):
                    self.setFont("Helvetica", 9)
                    # Optional left footer text (set by caller via class/instance attr)
                    try:
                        width, height = self._pagesize
                    except Exception:
                        width, height = (595.27, 841.89)  # default A4 portrait in points
                    left_margin = 40
                    right_margin = 40
                    footer_text_left = getattr(self, 'footer_text', None)
                    # Línea superior del pie (texto a la izquierda)
                    if footer_text_left:
                        self.drawString(left_margin, 28, footer_text_left)
                    # Paginación debajo del pie, alineada a la izquierda
                    text = f"Página {idx} de {num_pages}"
                    self.drawString(left_margin, 14, text)
                rl_canvas.Canvas.showPage(self)
            rl_canvas.Canvas.save(self)
except Exception:
    NumberedCanvas = None


def _get_format(request):
    return (request.GET.get('format') or '').lower() or 'html'


def _export_response(filename: str, content_type: str, data_bytes: bytes):
    resp = HttpResponse(data_bytes, content_type=content_type)
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


def _export_csv(title: str, headers: list[str], rows: list[list]):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([smart_str(title)])
    writer.writerow([datetime.now().strftime('%Y-%m-%d %H:%M')])
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return _export_response(f"{slugify(title)}.csv", "text/csv", output.getvalue().encode('utf-8'))


def _export_xlsx(title: str, headers: list[str], rows: list[list]):
    if Workbook is None:
        return HttpResponse("openpyxl no está instalado", status=500)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Datos'
    ws.append([title])
    ws.append([datetime.now().strftime('%Y-%m-%d %H:%M')])
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return _export_response(f"{slugify(title)}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buf.getvalue())


def _export_json(records: list[dict]):
    return JsonResponse(records, safe=False)


def _export_pdf(title: str, headers: list[str], rows: list[list], page_setup: dict | None = None):
    if NumberedCanvas is None:
        return HttpResponse("reportlab no está instalado", status=500)
    # Page setup
    paper = (page_setup or {}).get('paper', 'A4').upper()
    orientation = (page_setup or {}).get('orientation', 'portrait').lower()
    # Mapear tamaños de papel soportados
    PAPER_SIZES = {
        'A4': A4,
        'LETTER': LETTER,
        'LEGAL': LEGAL,
        # TABLOID: 11x17 pulgadas (792x1224 puntos)
        'TABLOID': (792, 1224),
    }
    base_size = PAPER_SIZES.get(paper, A4)
    pagesize = landscape(base_size) if orientation == 'landscape' else base_size
    buf = io.BytesIO()
    # Márgenes "Moderados": top ≈ 1" (72pt), left/right ≈ 0.75" (54pt)
    # En apaisada, reducir margen inferior para aprovechar el espacio al no tener pie
    bottom_margin = 48 if orientation == 'landscape' else 72
    doc = SimpleDocTemplate(
        buf,
        pagesize=pagesize,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=bottom_margin,
    )
    styles = getSampleStyleSheet()
    # Texto general (fecha, cuerpo) a 9 pt
    try:
        styles['Normal'].fontSize = 9
    except Exception:
        pass
    centered_heading = ParagraphStyle(
        name='CenteredHeading',
        parent=styles['Heading2'],
        alignment=TA_CENTER,
    )
    story = []

    # Logo: intentar localizar vía staticfiles finders (más robusto)
    logo_candidates = [
        'img/logo_tucan.png',
        'img/Logo Tucan_Mesa de trabajo 1.png',
        'img/logo.png',
    ]
    logo_path = None
    for candidate in logo_candidates:
        try:
            found = finders.find(candidate)
            if found:
                logo_path = found
                break
        except Exception:
            pass
    if logo_path:
        try:
            img = Image(logo_path, width=140, height=70)
            # Alinear el logo a la izquierda
            try:
                img.hAlign = 'LEFT'
            except Exception:
                pass
            story.append(img)
        except Exception:
            story.append(Paragraph("Imprenta Tucán", styles['Title']))
    else:
        story.append(Paragraph("Imprenta Tucán", styles['Title']))

    story.append(Paragraph(title, centered_heading))
    story.append(Paragraph(datetime.now().strftime('%Y-%m-%d %H:%M'), styles['Normal']))
    story.append(Spacer(1, 12))

    # Table
    data = [headers] + rows
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e5e7eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#9ca3af')),
    ]))
    story.append(table)

    # Configure footer text for the canvas (class attr so instances inherit it)
    if NumberedCanvas is not None:
        NumberedCanvas.footer_text = f"Imprenta Tucán — Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        # Ocultar pie de página en orientación apaisada (landscape)
        NumberedCanvas.hide_footer = (orientation == 'landscape')

    doc.build(story, canvasmaker=NumberedCanvas)
    return _export_response(f"{slugify(title)}.pdf", "application/pdf", buf.getvalue())


def slugify(text: str) -> str:
    return ''.join(c.lower() if c.isalnum() else '-' for c in text).strip('-')


def _export_dispatch(request, fmt: str, title: str, headers: list[str], rows: list[list], records: list[dict]):
    def _get_page_setup(req):
        return {
            'paper': (req.GET.get('paper') or 'A4').upper() if req else 'A4',
            'orientation': (req.GET.get('orientation') or 'portrait').lower() if req else 'portrait',
        }
    if fmt == 'csv':
        return _export_csv(title, headers, rows)
    if fmt in ('xlsx', 'excel'):
        return _export_xlsx(title, headers, rows)
    if fmt == 'json':
        return _export_json(records)
    if fmt == 'pdf':
        return _export_pdf(title, headers, rows, _get_page_setup(request))
    # html fallback
    return render(request, 'reportes/lista.html', {
        'title': title,
        'headers': headers,
        'rows': rows,
    })


def reporte_stock(request):
    fmt = _get_format(request)
    qs = Insumo.objects.filter(activo=True).order_by('nombre')
    headers = ['Código', 'Nombre', 'Categoría', 'Stock', 'Proveedor']

    # HTML: paginar con estilo del sistema
    if fmt == 'html':
        paginator = Paginator(qs, get_page_size())
        page = request.GET.get('page')
        page_obj = paginator.get_page(page)
        rows_page = [[i.codigo, i.nombre, i.categoria, i.stock, (i.proveedor.nombre if i.proveedor else '-') ] for i in page_obj.object_list]
        return render(request, 'reportes/lista.html', {
            'title': 'Stock disponible',
            'headers': headers,
            'rows_page': rows_page,
            'page_obj': page_obj,
            'preview_url': reverse('reporte_stock_preview'),
        })

    # Otros formatos: dataset completo
    rows = [[i.codigo, i.nombre, i.categoria, i.stock, (i.proveedor.nombre if i.proveedor else '-') ] for i in qs]
    records = [
        {
            'codigo': i.codigo,
            'nombre': i.nombre,
            'categoria': i.categoria,
            'stock': i.stock,
            'proveedor': i.proveedor.nombre if i.proveedor else None,
        }
        for i in qs
    ]
    return _export_dispatch(request, fmt, 'Stock disponible', headers, rows, records)


def reporte_proveedores_activos(request):
    fmt = _get_format(request)
    qs = Proveedor.objects.filter(activo=True).order_by('nombre')
    headers = ['Nombre', 'CUIT', 'Rubro', 'Email', 'Teléfono']
    if fmt == 'html':
        paginator = Paginator(qs, get_page_size())
        page = request.GET.get('page')
        page_obj = paginator.get_page(page)
        rows_page = [[p.nombre, p.cuit, (p.rubro_fk.nombre if p.rubro_fk else p.rubro), p.email, p.telefono] for p in page_obj.object_list]
        return render(request, 'reportes/lista.html', {
            'title': 'Proveedores activos',
            'headers': headers,
            'rows_page': rows_page,
            'page_obj': page_obj,
            'preview_url': reverse('reporte_proveedores_activos_preview'),
        })

    rows = [[p.nombre, p.cuit, (p.rubro_fk.nombre if p.rubro_fk else p.rubro), p.email, p.telefono] for p in qs]
    records = [
        {
            'nombre': p.nombre,
            'cuit': p.cuit,
            'rubro': p.rubro_fk.nombre if p.rubro_fk else p.rubro,
            'email': p.email,
            'telefono': p.telefono,
        }
        for p in qs
    ]
    return _export_dispatch(request, fmt, 'Proveedores activos', headers, rows, records)


def reporte_clientes_frecuentes(request):
    from django.db.models import Count

    fmt = _get_format(request)
    top = int(request.GET.get('top', '20') or 20)
    freq = (
        Pedido.objects.values('cliente')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')[:top]
    )
    cliente_ids = [f['cliente'] for f in freq]
    clientes_map = {c.id: c for c in Cliente.objects.filter(id__in=cliente_ids, estado='Activo')}

    headers = ['Cliente', 'Email', 'Pedidos', 'Puntaje estratégico']

    if fmt == 'html':
        paginator = Paginator(list(freq), get_page_size())
        page = request.GET.get('page')
        page_obj = paginator.get_page(page)
        rows_page = []
        for f in page_obj.object_list:
            c = clientes_map.get(f['cliente'])
            if not c:
                continue
            rows_page.append([f"{c.nombre} {c.apellido}", c.email, f['cnt'], c.puntaje_estrategico])
        return render(request, 'reportes/lista.html', {
            'title': 'Clientes frecuentes',
            'headers': headers,
            'rows_page': rows_page,
            'page_obj': page_obj,
            'preview_url': reverse('reporte_clientes_frecuentes_preview'),
        })

    rows, records = [], []
    for f in freq:
        c = clientes_map.get(f['cliente'])
        if not c:
            continue
        rows.append([f"{c.nombre} {c.apellido}", c.email, f['cnt'], c.puntaje_estrategico])
        records.append({
            'cliente': f"{c.nombre} {c.apellido}",
            'email': c.email,
            'pedidos': f['cnt'],
            'puntaje_estrategico': c.puntaje_estrategico,
        })

    return _export_dispatch(request, fmt, 'Clientes frecuentes', headers, rows, records)


def _preview_context(title: str, headers: list[str], rows: list[list]):
    # Intentar ubicar el logo en static con varios nombres posibles
    candidates = [
        'img/logo_tucan.png',
        'img/Logo Tucan_Mesa de trabajo 1.png',
        'img/logo.png',
    ]
    logo_static_path = None
    for cand in candidates:
        try:
            if finders.find(cand):
                logo_static_path = cand
                break
        except Exception:
            pass
    logo_url = static(logo_static_path) if logo_static_path else None
    return {
        'title': title,
        'headers': headers,
        'rows': rows,
        'generated_at': datetime.now(),
        'logo_url': logo_url,
    }


def preview_stock(request):
    qs = Insumo.objects.filter(activo=True).order_by('nombre')
    headers = ['Código', 'Nombre', 'Categoría', 'Stock', 'Proveedor']
    rows = [[i.codigo, i.nombre, i.categoria, i.stock, (i.proveedor.nombre if i.proveedor else '-') ] for i in qs]

    # Contexto base (sin paginación)
    ctx = _preview_context('Stock disponible', headers, rows)
    paper = (request.GET.get('paper') or 'A4').upper()
    orientation = (request.GET.get('orientation') or 'portrait').lower()
    ctx['paper'] = paper
    ctx['orientation'] = orientation
    ctx['export_pdf_url'] = reverse('reporte_stock') + f'?format=pdf&paper={paper}&orientation={orientation}'
    ctx['simple_preview'] = True  # ocultar controles de tamaño/orientación y etiqueta "Vista previa"
    # Solicitud: eliminar pie de página en esta vista previa (todas las orientaciones)
    ctx['hide_footer'] = True
    return render(request, 'reportes/preview.html', ctx)


def preview_proveedores_activos(request):
    qs = Proveedor.objects.filter(activo=True).order_by('nombre')
    headers = ['Nombre', 'CUIT', 'Rubro', 'Email', 'Teléfono']
    rows = [[p.nombre, p.cuit, (p.rubro_fk.nombre if p.rubro_fk else p.rubro), p.email, p.telefono] for p in qs]
    ctx = _preview_context('Proveedores activos', headers, rows)
    paper = (request.GET.get('paper') or 'A4').upper()
    orientation = (request.GET.get('orientation') or 'portrait').lower()
    ctx['paper'] = paper
    ctx['orientation'] = orientation
    ctx['export_pdf_url'] = reverse('reporte_proveedores_activos') + f'?format=pdf&paper={paper}&orientation={orientation}'
    ctx['simple_preview'] = True
    # Solicitud: eliminar pie de página en paisaje para esta vista previa
    if orientation == 'landscape':
        ctx['hide_footer'] = True
    return render(request, 'reportes/preview.html', ctx)


def preview_clientes_frecuentes(request):
    from django.db.models import Count

    top = int(request.GET.get('top', '20') or 20)
    freq = (
        Pedido.objects.values('cliente')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')[:top]
    )
    cliente_ids = [f['cliente'] for f in freq]
    clientes_map = {c.id: c for c in Cliente.objects.filter(id__in=cliente_ids, estado='Activo')}

    headers = ['Cliente', 'Email', 'Pedidos', 'Puntaje estratégico']
    rows = []
    for f in freq:
        c = clientes_map.get(f['cliente'])
        if not c:
            continue
        rows.append([f"{c.nombre} {c.apellido}", c.email, f['cnt'], c.puntaje_estrategico])

    ctx = _preview_context('Clientes frecuentes', headers, rows)
    paper = (request.GET.get('paper') or 'A4').upper()
    orientation = (request.GET.get('orientation') or 'portrait').lower()
    ctx['paper'] = paper
    ctx['orientation'] = orientation
    ctx['simple_preview'] = True
    # Mejorar diseño de controles en esta vista
    ctx['controls_variant'] = 'pill'
    # Solicitud: eliminar pie de página en paisaje para esta vista previa
    if orientation == 'landscape':
        ctx['hide_footer'] = True
    return render(request, 'reportes/preview.html', ctx)
