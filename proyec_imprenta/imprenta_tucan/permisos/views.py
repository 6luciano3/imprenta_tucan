from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Permiso
from configuracion.permissions import require_perm
from .forms import PermisoForm


@require_perm('Permisos', 'Listar')
def lista_permisos(request):
    # Unificar parámetros y patrón de lista
    query = request.GET.get('q', '') or request.GET.get('criterio', '')
    order_by = request.GET.get('order_by', 'id')
    direction = request.GET.get('direction', 'asc')

    valid_order_fields = ['id', 'nombre', 'descripcion', 'modulo', 'estado']
    if order_by not in valid_order_fields:
        order_by = 'id'

    qs = Permiso.objects.all()
    if query:
        qs = qs.filter(
            Q(nombre__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(modulo__icontains=query) |
            Q(estado__icontains=query)
        )

    order_field = f'-{order_by}' if direction == 'desc' else order_by
    qs = qs.order_by(order_field)

    from configuracion.services import get_page_size
    paginator = Paginator(qs, get_page_size())
    page = request.GET.get('page')
    permisos = paginator.get_page(page)

    return render(request, 'permisos/lista_permisos.html', {
        'permisos': permisos,
        'query': query,
        'order_by': order_by,
        'direction': direction,
    })


@require_perm('Permisos', 'Crear')
def alta_permiso(request):
    # Acciones sugeridas "válidas" para facilitar carga
    acciones_sugeridas = [
        'Crear', 'Listar', 'Ver', 'Editar', 'Actualizar', 'Eliminar',
        'Activar', 'Desactivar', 'Aprobar', 'Rechazar', 'Exportar',
        'Importar', 'Imprimir', 'Descargar'
    ]
    modulos_sugeridos = ['Auditoria', 'Configuracion', 'Presupuesto']

    form = PermisoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'El permiso ha sido registrado correctamente.')
        return redirect('lista_permisos')
    elif request.method == 'POST' and not form.is_valid():
        messages.error(request, 'Hay errores en el formulario. Por favor, revisa los campos.')
    return render(request, 'permisos/alta_permiso.html', {
        'form': form,
        'acciones_sugeridas': acciones_sugeridas,
        'modulos_sugeridos': ['Auditoria', 'Configuracion', 'Presupuesto']
    })


@require_perm('Permisos', 'Editar')
def modificar_permiso(request, idPermiso):
    permiso = get_object_or_404(Permiso, id=idPermiso)
    # Acciones sugeridas para facilitar edición (mismas que en alta)
    acciones_sugeridas = [
        'Crear', 'Listar', 'Ver', 'Editar', 'Actualizar', 'Eliminar',
        'Activar', 'Desactivar', 'Aprobar', 'Rechazar', 'Exportar',
        'Importar', 'Imprimir', 'Descargar'
    ]
    form = PermisoForm(request.POST or None, instance=permiso)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'El permiso ha sido modificado correctamente.')
            return redirect('lista_permisos')
        else:
            # Construir detalle de errores para mensaje agregado
            detalles = []
            for campo, errores in form.errors.items():
                for err in errores:
                    detalles.append(f"{campo}: {err}")
            if detalles:
                messages.error(request, 'Datos inválidos: ' + '; '.join(detalles))
    return render(request, 'permisos/modificar_permiso.html', {
        'form': form,
        'permiso': permiso,
        'acciones_sugeridas': acciones_sugeridas,
    })


@require_perm('Permisos', 'Desactivar')
def baja_permiso(request, idPermiso):
    permiso = get_object_or_404(Permiso, id=idPermiso)
    if request.method == 'POST':
        permiso.estado = 'Inactivo'
        permiso.save()
        return redirect('lista_permisos')
    return render(request, 'permisos/baja_permiso.html', {'permiso': permiso})


@require_perm('Permisos', 'Activar')
def reactivar_permiso(request, idPermiso):
    permiso = get_object_or_404(Permiso, id=idPermiso)
    if request.method == 'POST':
        permiso.estado = 'Activo'
        permiso.save()
        return redirect('lista_permisos')
    return render(request, 'permisos/reactivar_permiso.html', {'permiso': permiso})


@require_perm('Permisos', 'Listar')
def buscar_permiso(request):
    resultados = []
    criterio = ''
    if request.method == 'POST':
        criterio = (request.POST.get('criterio_busqueda') or '').strip()
        if not criterio:
            messages.error(request, 'Debe ingresar un criterio de búsqueda.')
        else:
            resultados = Permiso.objects.filter(
                Q(nombre__icontains=criterio) |
                Q(descripcion__icontains=criterio) |
                Q(modulo__icontains=criterio) |
                Q(acciones__icontains=criterio)
            ).order_by('id')
            # Preparar representación amigable de acciones para la plantilla
            for p in resultados:
                acciones_raw = p.acciones
                acciones_list = []
                if isinstance(acciones_raw, (list, tuple)):
                    acciones_list = [a.strip() for a in acciones_raw if isinstance(a, str) and a.strip()]
                elif isinstance(acciones_raw, str):
                    acciones_list = [a.strip() for a in acciones_raw.replace('\n', ',').split(',') if a.strip()]
                p.acciones_csv = ', '.join(acciones_list) if acciones_list else ''
            if not resultados:
                messages.error(request, 'No se encontraron permisos que coincidan con el criterio de búsqueda.')
    return render(request, 'permisos/buscar_permiso.html', {
        'lista_resultados': resultados,
        'criterio': criterio,
    })


@require_perm('Permisos', 'Ver')
def detalle_permiso(request, id):
    permiso = get_object_or_404(Permiso, id=id)
    # Normalizar acciones para mostrarlas sin lógica de tipos en la plantilla
    acciones_raw = permiso.acciones
    acciones_list = []
    if isinstance(acciones_raw, (list, tuple)):
        acciones_list = [a.strip() for a in acciones_raw if isinstance(a, str) and a.strip()]
    elif isinstance(acciones_raw, str):
        acciones_list = [a.strip() for a in acciones_raw.replace('\n', ',').split(',') if a.strip()]
    acciones_csv = ', '.join(acciones_list) if acciones_list else ''

    return render(request, 'permisos/detalle_permiso.html', {
        'permiso': permiso,
        'acciones_list': acciones_list,
        'acciones_csv': acciones_csv,
    })
