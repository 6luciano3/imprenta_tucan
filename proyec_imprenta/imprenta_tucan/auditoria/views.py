from django.shortcuts import redirect, get_object_or_404
from .models import AuditEntry
from django.shortcuts import render
from django.contrib import messages
from django.core.paginator import Paginator


def ver_auditoria(request, pk):
    auditoria = get_object_or_404(AuditEntry, pk=pk)
    return render(request, 'auditoria/detalle_auditoria.html', {'auditoria': auditoria})


def lista_auditoria(request):
    auditorias = AuditEntry.objects.exclude(user=None)
    modelo = request.GET.get('modelo', '').strip()
    evento = request.GET.get('evento', '').strip()
    usuario = request.GET.get('usuario', '').strip()
    fecha = request.GET.get('fecha', '').strip()

    if modelo:
        auditorias = auditorias.filter(model__icontains=modelo)
    if evento:
        auditorias = auditorias.filter(action=evento)
    if usuario:
        # Si usuario es un número (ID), buscar por user_id exacto. Si es texto, buscar por email exacto.
        if usuario.isdigit():
            auditorias = auditorias.filter(user_id=usuario)
        else:
            auditorias = auditorias.filter(user__email=usuario)
    if fecha:
        auditorias = auditorias.filter(timestamp__date=fecha)

    auditorias = auditorias.order_by('-timestamp')

    # Paginación consistente con otras listas
    try:
        from configuracion.services import get_page_size
        page_size = get_page_size()
    except Exception:
        page_size = 10
    paginator = Paginator(auditorias, page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'auditoria/lista_auditoria.html', {
        'auditorias': page_obj,
        'modelo': modelo,
        'evento': evento,
        'usuario': usuario,
        'fecha': fecha,
    })


def eliminar_auditoria(request, pk):
    auditoria = get_object_or_404(AuditEntry, pk=pk)
    if request.method == 'POST':
        auditoria.delete()
        messages.success(request, 'Registro de auditoría eliminado correctamente.')
        return redirect('lista_auditoria')
    return render(request, 'auditoria/confirmar_eliminacion.html', {'auditoria': auditoria})
