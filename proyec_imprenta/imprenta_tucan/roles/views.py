from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Rol
from .forms import RolForm
from django.contrib import messages
from configuracion.permissions import require_perm


@require_perm('Roles', 'Listar')
def lista_roles(request):
    # Parámetros unificados
    query = request.GET.get('q', '') or request.GET.get('criterio', '')
    order_by = request.GET.get('order_by', 'nombreRol')
    direction = request.GET.get('direction', 'asc')

    valid_order_fields = ['idRol', 'nombreRol', 'descripcion', 'estado']
    if order_by not in valid_order_fields:
        order_by = 'nombreRol'

    qs = Rol.objects.all()
    if query:
        qs = qs.filter(
            Q(nombreRol__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(estado__icontains=query)
        )

    order_field = f'-{order_by}' if direction == 'desc' else order_by
    qs = qs.order_by(order_field)

    from configuracion.services import get_page_size
    paginator = Paginator(qs, get_page_size())
    page = request.GET.get('page')
    roles = paginator.get_page(page)

    return render(request, 'roles/lista_roles.html', {
        'roles': roles,
        'query': query,
        'order_by': order_by,
        'direction': direction,
    })


@require_perm('Roles', 'Crear')
def alta_rol(request):
    # Sin valores iniciales: los campos deben mostrarse vacíos. Mostrar todos los permisos activos.
    form = RolForm(request.POST or None, show_all_permissions=True)
    # Precalcular IDs seleccionados para mantener checks tras error sin usar getlist en plantilla
    selected_perm_ids = set()
    if request.method == 'POST':
        try:
            selected_perm_ids = {int(x) for x in request.POST.getlist('permisos')}
        except ValueError:
            selected_perm_ids = set()
    if request.method == 'POST':
        if form.is_valid():
            rol = form.save()
            messages.success(request, 'El rol ha sido registrado correctamente.')
            return redirect('lista_roles')
        else:
            # Mensaje de error global con detalle
            detalles = []
            for campo, errores in form.errors.items():
                for err in errores:
                    detalles.append(f"{campo}: {err}")
            if detalles:
                messages.error(request, 'Datos inválidos: ' + '; '.join(detalles))
    return render(request, 'roles/alta_rol.html', {'form': form, 'selected_perm_ids': selected_perm_ids})


@require_perm('Roles', 'Editar')
def modificar_rol(request, idRol):
    rol = get_object_or_404(Rol, idRol=idRol)
    selected_perm_ids = set()
    if request.method == 'POST':
        form = RolForm(request.POST, instance=rol, show_all_permissions=True)
        # IDs marcados enviados en el POST (para mantener estado en errores)
        try:
            selected_perm_ids = {int(x) for x in request.POST.getlist('permisos')}
        except ValueError:
            selected_perm_ids = set()
        if form.is_valid():
            form.save()
            messages.success(request, 'El rol ha sido modificado correctamente.')
            return redirect('lista_roles')
        else:
            detalles = []
            for campo, errores in form.errors.items():
                for err in errores:
                    detalles.append(f"{campo}: {err}")
            if detalles:
                messages.error(request, 'Datos inválidos: ' + '; '.join(detalles))
    else:
        form = RolForm(instance=rol, show_all_permissions=True)
        selected_perm_ids = set(rol.permisos.values_list('id', flat=True))

    # Deserializar acciones para cada permiso
    import json
    permisos_qs = form.fields['permisos'].queryset
    for permiso in permisos_qs:
        try:
            permiso.acciones_list = json.loads(permiso.acciones) if permiso.acciones else []
        except Exception:
            permiso.acciones_list = []
    return render(request, 'roles/modificar_rol.html', {
        'form': form,
        'rol': rol,
        'selected_perm_ids': selected_perm_ids,
    })


@require_perm('Roles', 'Eliminar')
def eliminar_rol(request, idRol):
    rol = get_object_or_404(Rol, idRol=idRol)
    if request.method == 'POST':
        rol.delete()
        return redirect('lista_roles')
    return render(request, 'roles/eliminar_rol.html', {'rol': rol})


@require_perm('Roles', 'Editar')
def desactivar_rol(request, idRol):
    rol = get_object_or_404(Rol, idRol=idRol)
    if request.method == 'POST':
        rol.estado = 'Inactivo'
        rol.save()
        return redirect('lista_roles')
    return render(request, 'roles/desactivar_rol.html', {'rol': rol})


@require_perm('Roles', 'Editar')
def reactivar_rol(request, idRol):
    rol = get_object_or_404(Rol, idRol=idRol)
    if request.method == 'POST':
        rol.estado = 'Activo'
        rol.save()
        return redirect('lista_roles')
    return render(request, 'roles/reactivar_rol.html', {'rol': rol})
