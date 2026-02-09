from django.shortcuts import redirect, get_object_or_404
from .models import AuditEntry
from django.shortcuts import render
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
import csv
from urllib.parse import urlencode
from io import BytesIO


def ver_auditoria(request, pk):
    auditoria = get_object_or_404(AuditEntry, pk=pk)
    return render(request, 'auditoria/detalle_auditoria.html', {'auditoria': auditoria})


def _filtrar_auditorias(request):
    """Aplica filtros comunes para lista y exportación."""
    qs = AuditEntry.objects.exclude(user=None)
    app = request.GET.get('app', '').strip()
    modelo = request.GET.get('modelo', '').strip()
    evento = request.GET.get('evento', '').strip()
    usuario = request.GET.get('usuario', '').strip()
    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    categoria = request.GET.get('categoria', '').strip()  # ej: stock-movement

    if app:
        qs = qs.filter(app_label__icontains=app)
    if modelo:
        qs = qs.filter(model__icontains=modelo)
    if evento:
        qs = qs.filter(action=evento)
    if usuario:
        # Si usuario es un número (ID), buscar por user_id exacto. Si es texto, buscar por email exacto.
        if usuario.isdigit():
            qs = qs.filter(user_id=usuario)
        else:
            qs = qs.filter(user__email=usuario)
    if fecha_desde:
        qs = qs.filter(timestamp__date__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(timestamp__date__lte=fecha_hasta)
    if categoria:
        # Filtrar por contenido en extra (JSON como texto) que contenga la categoría
        qs = qs.filter(extra__icontains=f'"category": "{categoria}"')
    return qs


def lista_auditoria(request):
    auditorias = _filtrar_auditorias(request).order_by('-timestamp')

    # Paginación consistente con otras listas
    try:
        from configuracion.services import get_page_size
        page_size = get_page_size()
    except Exception:
        page_size = 10
    paginator = Paginator(auditorias, page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Preservar querystring para exportar
    export_qs = request.GET.copy()
    if 'page' in export_qs:
        export_qs.pop('page')
    export_url_params = urlencode(export_qs)

    return render(request, 'auditoria/lista_auditoria.html', {
        'auditorias': page_obj,
        'export_params': export_url_params,
    })


def eliminar_auditoria(request, pk):
    auditoria = get_object_or_404(AuditEntry, pk=pk)
    if request.method == 'POST':
        auditoria.delete()
        messages.success(request, 'Registro de auditoría eliminado correctamente.')
        return redirect('lista_auditoria')
    return render(request, 'auditoria/confirmar_eliminacion.html', {'auditoria': auditoria})


def exportar_auditoria_csv(request):
    """Exporta la auditoría filtrada a CSV."""
    auditorias = _filtrar_auditorias(request).order_by('-timestamp')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="auditoria.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'timestamp', 'usuario_email', 'app_label', 'model', 'object_id', 'action',
        'path', 'method', 'ip_address', 'changes', 'extra'
    ])
    for a in auditorias:
        writer.writerow([
            a.timestamp.isoformat(),
            getattr(a.user, 'email', '') if a.user else '',
            a.app_label,
            a.model,
            a.object_id,
            a.action,
            a.path,
            a.method,
            a.ip_address or '',
            (a.changes or '').replace('\r', ' ').replace('\n', ' '),
            (a.extra or '').replace('\r', ' ').replace('\n', ' '),
        ])
    return response


def exportar_auditoria_xlsx(request):
    """Exporta la auditoría filtrada a Excel (XLSX)."""
    auditorias = _filtrar_auditorias(request).order_by('-timestamp')
    try:
        import openpyxl
        from openpyxl.utils import get_column_letter
    except Exception:
        # Fallback a CSV si openpyxl no está disponible
        return exportar_auditoria_csv(request)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Auditoria"

    headers = [
        'timestamp', 'usuario_email', 'app_label', 'model', 'object_id', 'action',
        'path', 'method', 'ip_address', 'changes', 'extra'
    ]
    ws.append(headers)

    # Escribir filas
    for a in auditorias:
        ws.append([
            a.timestamp.isoformat(),
            getattr(a.user, 'email', '') if a.user else '',
            a.app_label,
            a.model,
            a.object_id,
            a.action,
            a.path,
            a.method,
            a.ip_address or '',
            (a.changes or ''),
            (a.extra or ''),
        ])

    # Ajustar anchos de columna de forma básica
    for col_idx, header in enumerate(headers, start=1):
        max_len = len(header)
        for row in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
            cell_val = row[0].value
            if cell_val is None:
                continue
            try:
                val_len = len(str(cell_val))
            except Exception:
                val_len = 0
            if val_len > max_len:
                max_len = min(val_len, 80)  # límite razonable
        ws.column_dimensions[get_column_letter(col_idx)].width = max(12, max_len + 2)

    # Volcar a bytes
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="auditoria.xlsx"'
    return response
