from django.http import HttpResponse, JsonResponse
from permisos.decorators import requiere_permiso

from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.management import call_command
from django.template.loader import render_to_string
from .models import Proveedor, Rubro
from automatizacion.models import ScoreProveedor
from .forms import ProveedorForm, RubroForm


@login_required
def index(request):
    return redirect('lista_proveedores')


@login_required
@requiere_permiso("Proveedores")
def lista_proveedores(request):
    """Lista de proveedores unificada con búsqueda y ordenamiento (reemplaza "buscar")."""
    # Parámetros unificados: usar 'q' y aceptar 'criterio' como alias de compatibilidad
    query = request.GET.get('q', '') or request.GET.get('criterio', '')
    order_by = request.GET.get('order_by', 'nombre')
    direction = request.GET.get('direction', 'asc')

    valid_order_fields = ['id', 'nombre', 'cuit', 'email', 'telefono', 'rubro', 'direccion']
    if order_by not in valid_order_fields:
        order_by = 'nombre'

    proveedores_qs = Proveedor.objects.all()

    if query:
        if order_by == 'id' and query.isdigit():
            proveedores_qs = proveedores_qs.filter(id=int(query))
        else:
            proveedores_qs = proveedores_qs.filter(
                Q(nombre__icontains=query) |
                Q(cuit__icontains=query) |
                Q(email__icontains=query) |
                Q(telefono__icontains=query) |
                Q(rubro__icontains=query) |
                Q(rubro_fk__nombre__icontains=query) |
                Q(direccion__icontains=query)
            )

    order_field = f'-{order_by}' if direction == 'desc' else order_by
    proveedores_qs = proveedores_qs.order_by(order_field)

    from configuracion.services import get_page_size
    paginator = Paginator(proveedores_qs, get_page_size())
    page = request.GET.get('page')
    proveedores = paginator.get_page(page)

    # Mapa de scores por proveedor para mostrar "Ranking cargado" en la lista
    proveedor_ids = [p.id for p in proveedores.object_list]
    scores_qs = ScoreProveedor.objects.filter(proveedor_id__in=proveedor_ids)
    scores_map = {s.proveedor_id: s.score for s in scores_qs}

    # Top 10 ranking: solo proveedores cuyos insumos sean todos "directos"
    # (tienen al menos 1 directo y ningún indirecto)
    from django.db.models import Count, Q as DQ
    scores_ranking = (
        ScoreProveedor.objects
        .annotate(
            n_directos=Count('proveedor__insumos', filter=DQ(proveedor__insumos__tipo='directo')),
            n_indirectos=Count('proveedor__insumos', filter=DQ(proveedor__insumos__tipo='indirecto')),
        )
        .filter(n_directos__gt=0, n_indirectos=0)
        .select_related('proveedor', 'proveedor__rubro_fk')
        .order_by('-score')[:10]
    )

    return render(request, 'proveedores/lista_proveedores.html', {
        'proveedores': proveedores,
        'query': query,
        'order_by': order_by,
        'direction': direction,
        'scores_map': scores_map,
        'scores_ranking': scores_ranking,
    })


@login_required
@requiere_permiso("Proveedores", "Crear")
def crear_proveedor(request):
    """Crear nuevo proveedor"""
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            proveedor = form.save()
            messages.success(request, f'El proveedor {proveedor.nombre} ha sido creado exitosamente.')
            return redirect('lista_proveedores')
    else:
        form = ProveedorForm()
    rubros = Rubro.objects.filter(activo=True).order_by('nombre')
    return render(request, 'proveedores/crear_proveedor.html', {'form': form, 'rubros': rubros})


@login_required
@requiere_permiso("Proveedores", "Editar")
def editar_proveedor(request, id):
    """Editar proveedor existente"""
    proveedor = get_object_or_404(Proveedor, id=id)

    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, f'El proveedor {proveedor.nombre} ha sido actualizado exitosamente.')
            return redirect('lista_proveedores')
    else:
        form = ProveedorForm(instance=proveedor)

    rubros = Rubro.objects.filter(activo=True).order_by('nombre')
    return render(request, 'proveedores/editar_proveedor.html', {'form': form, 'proveedor': proveedor, 'rubros': rubros})


@login_required
@requiere_permiso("Proveedores", "Eliminar")
def eliminar_proveedor(request, id):
    """Eliminar proveedor con confirmación"""
    proveedor = get_object_or_404(Proveedor, id=id)

    if request.method == 'POST':
        proveedor.activo = False
        proveedor.save()
        messages.success(request, f'El proveedor {proveedor.nombre} ha sido desactivado.')
        return redirect('lista_proveedores')

    return redirect('lista_proveedores')


@login_required
@requiere_permiso("Proveedores")
def detalle_proveedor(request, id):
    """Ver detalles completos del proveedor"""
    proveedor = get_object_or_404(Proveedor, id=id)
    from compras.models import OrdenPago, HistorialPrecioInsumo
    ordenes_pago = OrdenPago.objects.filter(proveedor=proveedor).order_by('-creado_en')[:10]
    historial_precios = (
        HistorialPrecioInsumo.objects
        .filter(remito__proveedor=proveedor)
        .select_related('insumo', 'remito')
        .order_by('-fecha')[:15]
    )
    return render(request, 'proveedores/detalle_proveedor.html', {
        'proveedor': proveedor,
        'ordenes_pago': ordenes_pago,
        'historial_precios': historial_precios,
    })


@login_required
@requiere_permiso("Proveedores", "Activar")
def activar_proveedor(request, id):
    """Activar/desactivar proveedor"""
    proveedor = get_object_or_404(Proveedor, id=id)

    if request.method == 'POST':
        proveedor.activo = not proveedor.activo
        proveedor.save()

        estado = "activado" if proveedor.activo else "desactivado"
        messages.success(request, f'El proveedor {proveedor.nombre} ha sido {estado}.')
        return redirect('lista_proveedores')

    return redirect('lista_proveedores')


@login_required
@user_passes_test(lambda u: u.is_staff)
def seed_proveedores_ui(request):
    """Carga proveedores de prueba desde la UI (solo staff)."""
    if request.method != 'POST':
        return redirect('lista_proveedores')

    count = 30
    try:
        call_command('seed_proveedores', count=count)
        messages.success(request, f'Se cargaron {count} proveedores de prueba correctamente.')
    except Exception as e:
        messages.error(request, f'Error al cargar proveedores de prueba: {e}')
    return redirect('lista_proveedores')


@login_required
@requiere_permiso("Proveedores")
def alta_proveedor(request):
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_proveedores')  # Redirigir a la lista de proveedores después de guardar
    else:
        form = ProveedorForm()
    return render(request, 'proveedores/alta_proveedor.html', {'form': form})

# =============================
# CRUD Rubros (Industria Gráfica)
# =============================


@login_required
@requiere_permiso("Proveedores")
def lista_rubros(request):
    # Si la petición es AJAX, devolver solo la tabla paginada
    query = request.GET.get('q', '').strip()
    order_by = request.GET.get('order_by', 'nombre')
    direction = request.GET.get('direction', 'asc')
    qs = Rubro.objects.all()
    if query:
        qs = qs.filter(Q(nombre__icontains=query) | Q(descripcion__icontains=query))
    order_field = f'-{order_by}' if direction == 'desc' else order_by
    qs = qs.order_by(order_field)
    from configuracion.services import get_page_size
    paginator = Paginator(qs, get_page_size())
    page = request.GET.get('page')
    rubros = paginator.get_page(page)
    # Usar el queryset paginado para el modal
    rubros_modal = rubros
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('popup') == '1':
        # Solo devolver la tabla para el modal, nunca el dashboard
        html = render_to_string('proveedores/tabla_rubros_modal.html', {'rubros': rubros, 'request': request})
        return HttpResponse(html, content_type='text/html')
    # Renderizar solo la tabla si se solicita desde el modal
    if request.GET.get('popup') == '1':
        return render(request, 'proveedores/tabla_rubros_modal.html', {'rubros': rubros, 'request': request})
    # Renderizar la página completa solo si no es modal
    return render(request, 'proveedores/rubros_lista.html', {
        'rubros': rubros,
        'rubros_modal': rubros_modal,
        'query': query,
        'order_by': order_by,
        'direction': direction,
    })


@login_required
@requiere_permiso("Proveedores")
def crear_rubro(request):
    if request.method == 'POST':
        form = RubroForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Rubro creado correctamente.')
            url = 'lista_rubros'
            return redirect(url)
    else:
        form = RubroForm()
    return render(request, 'proveedores/rubro_form.html', {'form': form, 'modo': 'crear'})


@login_required
@requiere_permiso("Proveedores")
def editar_rubro(request, pk):
    rubro = get_object_or_404(Rubro, pk=pk)
    if request.method == 'POST':
        form = RubroForm(request.POST, instance=rubro)
        if form.is_valid():
            form.save()
            messages.success(request, 'Rubro actualizado correctamente.')
            return redirect('lista_rubros')
    else:
        form = RubroForm(instance=rubro)
    return render(request, 'proveedores/rubro_form.html', {'form': form, 'modo': 'editar', 'rubro': rubro})


@login_required
@requiere_permiso("Proveedores")
def eliminar_rubro(request, pk):
    rubro = get_object_or_404(Rubro, pk=pk)
    proveedores_asociados = rubro.proveedores.filter(activo=True).count()
    if proveedores_asociados:
        messages.error(
            request,
            f'No se puede eliminar el rubro "{rubro.nombre}" porque tiene '
            f'{proveedores_asociados} proveedor(es) activo(s) asociado(s).'
        )
        return redirect('lista_rubros')
    if request.method == 'POST':
        rubro.delete()
        messages.success(request, 'Rubro eliminado correctamente.')
        return redirect('lista_rubros')
    return render(request, 'proveedores/rubro_eliminar_confirm.html', {'rubro': rubro})


@login_required
def buscar_proveedor(request):
    """Vista legacy: redirige a la lista unificada preservando querystring."""
    params = request.GET.urlencode()
    url = f"/proveedores/lista/"
    if params:
        url = f"{url}?{params}"
    return redirect(url)


# =============================
# Respuesta del proveedor a Orden de Compra (vía token, sin login)
# =============================

def orden_compra_confirmar(request, token):
    """El proveedor confirma la orden haciendo clic en el link del email."""
    from compras.models import OrdenCompra, EstadoCompra
    orden = get_object_or_404(OrdenCompra.objects.select_related('estado', 'proveedor'), token_proveedor=token)

    ya_respondida = orden.estado and orden.estado.nombre.lower() in ('confirmada', 'recibida', 'rechazada', 'cancelada')

    if request.method == 'POST' and not ya_respondida:
        estado_confirmada, _ = EstadoCompra.objects.get_or_create(nombre='Confirmada')
        obs_anterior = orden.observaciones or ''
        orden.estado = estado_confirmada
        orden.observaciones = (obs_anterior + '\n' if obs_anterior else '') + 'Confirmada por el proveedor vía email.'
        orden.save(update_fields=['estado', 'observaciones'])
        return render(request, 'proveedores/orden_accion_realizada.html', {
            'orden': orden,
            'accion': 'confirmada',
            'proveedor': orden.proveedor,
        })

    return render(request, 'proveedores/orden_confirmar.html', {
        'orden': orden,
        'proveedor': orden.proveedor,
        'ya_respondida': ya_respondida,
    })


def orden_compra_rechazar(request, token):
    """El proveedor rechaza la orden haciendo clic en el link del email."""
    from compras.models import OrdenCompra, EstadoCompra
    orden = get_object_or_404(OrdenCompra.objects.select_related('estado', 'proveedor'), token_proveedor=token)

    ya_respondida = orden.estado and orden.estado.nombre.lower() in ('confirmada', 'recibida', 'rechazada', 'cancelada')

    if request.method == 'POST' and not ya_respondida:
        motivo = request.POST.get('motivo', '').strip()
        estado_rechazada, _ = EstadoCompra.objects.get_or_create(nombre='Rechazada')
        obs_anterior = orden.observaciones or ''
        orden.estado = estado_rechazada
        orden.observaciones = (obs_anterior + '\n' if obs_anterior else '') + f'Rechazada por el proveedor vía email. Motivo: {motivo or "Sin motivo"}'
        orden.save(update_fields=['estado', 'observaciones'])
        return render(request, 'proveedores/orden_accion_realizada.html', {
            'orden': orden,
            'accion': 'rechazada',
            'proveedor': orden.proveedor,
            'motivo': motivo,
        })

    return render(request, 'proveedores/orden_rechazar.html', {
        'orden': orden,
        'proveedor': orden.proveedor,
        'ya_respondida': ya_respondida,
    })
