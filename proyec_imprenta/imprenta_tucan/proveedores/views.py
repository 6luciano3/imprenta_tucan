from django.http import HttpResponse, JsonResponse
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


def index(request):
    return HttpResponse("Página de ejemplo de la app")


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

    return render(request, 'proveedores/lista_proveedores.html', {
        'proveedores': proveedores,
        'query': query,
        'order_by': order_by,
        'direction': direction,
        'scores_map': scores_map,
    })


def crear_proveedor(request):
    """Crear nuevo proveedor"""
    if request.method == 'POST':
        # Procesar formulario
        nombre = request.POST.get('nombre')
        cuit = request.POST.get('cuit')
        email = request.POST.get('email')
        telefono = request.POST.get('telefono')
        direccion = request.POST.get('direccion')
        # Preferir selección del catálogo si viene informada
        rubro_lookup_id = request.POST.get('rubro_lookup')
        rubro_text = request.POST.get('rubro')
        rubro = rubro_text
        rubro_fk = None
        if rubro_lookup_id:
            try:
                rubro_obj = Rubro.objects.get(pk=rubro_lookup_id)
                rubro = rubro_obj.nombre
                rubro_fk = rubro_obj
            except Rubro.DoesNotExist:
                pass
        elif rubro_text:
            # Intentar mapear texto a FK
            try:
                rubro_fk = Rubro.objects.get(nombre__iexact=rubro_text.strip())
            except Rubro.DoesNotExist:
                rubro_fk = None

        if nombre and email and telefono:
            Proveedor.objects.create(
                nombre=nombre,
                cuit=cuit,
                email=email,
                telefono=telefono,
                direccion=direccion,
                rubro=rubro,
                rubro_fk=rubro_fk
            )
            messages.success(request, f'El proveedor {nombre} ha sido creado exitosamente.')
            return redirect('lista_proveedores')
        else:
            messages.error(request, 'Por favor complete todos los campos obligatorios.')

    rubros = Rubro.objects.filter(activo=True).order_by('nombre')
    return render(request, 'proveedores/crear_proveedor.html', {'rubros': rubros})


def editar_proveedor(request, id):
    """Editar proveedor existente"""
    proveedor = get_object_or_404(Proveedor, id=id)

    if request.method == 'POST':
        # Procesar formulario de edición
        proveedor.nombre = request.POST.get('nombre', proveedor.nombre)
        proveedor.cuit = request.POST.get('cuit', proveedor.cuit)
        proveedor.email = request.POST.get('email', proveedor.email)
        proveedor.telefono = request.POST.get('telefono', proveedor.telefono)
        proveedor.direccion = request.POST.get('direccion', proveedor.direccion)
        proveedor.rubro = request.POST.get('rubro', proveedor.rubro)
        rubro_lookup_id = request.POST.get('rubro_lookup')
        if rubro_lookup_id:
            try:
                proveedor.rubro_fk = Rubro.objects.get(pk=rubro_lookup_id)
                proveedor.rubro = proveedor.rubro_fk.nombre
            except Rubro.DoesNotExist:
                pass
        elif proveedor.rubro:
            # Mapear texto a FK si existe catálogo
            try:
                proveedor.rubro_fk = Rubro.objects.get(nombre__iexact=proveedor.rubro.strip())
            except Rubro.DoesNotExist:
                proveedor.rubro_fk = None

        proveedor.save()
        messages.success(request, f'El proveedor {proveedor.nombre} ha sido actualizado exitosamente.')
        return redirect('lista_proveedores')

    rubros = Rubro.objects.filter(activo=True).order_by('nombre')
    return render(request, 'proveedores/editar_proveedor.html', {'proveedor': proveedor, 'rubros': rubros})


def eliminar_proveedor(request, id):
    """Eliminar proveedor con confirmación"""
    proveedor = get_object_or_404(Proveedor, id=id)

    if request.method == 'POST':
        nombre_proveedor = proveedor.nombre
        rubro_proveedor = proveedor.rubro or "Sin rubro"
        proveedor.delete()
        messages.success(
            request, f'El proveedor {nombre_proveedor} ({rubro_proveedor}) ha sido eliminado exitosamente.')
        return redirect('lista_proveedores')

    return render(request, 'proveedores/confirmar_eliminacion.html', {'proveedor': proveedor})


def detalle_proveedor(request, id):
    """Ver detalles completos del proveedor"""
    proveedor = get_object_or_404(Proveedor, id=id)
    return render(request, 'proveedores/detalle_proveedor.html', {'proveedor': proveedor})


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


def lista_rubros(request):
    # Si la petición es AJAX, devolver solo la tabla paginada
    query = request.GET.get('q', '').strip()
    order_by = request.GET.get('order_by', 'nombre')
    direction = request.GET.get('direction', 'asc')
    qs = Rubro.objects.all()
    if query:
        from django.db.models import Q
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
        from django.http import HttpResponse
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


def eliminar_rubro(request, pk):
    rubro = get_object_or_404(Rubro, pk=pk)
    if request.method == 'POST':
        rubro.delete()
        messages.success(request, 'Rubro eliminado correctamente.')
        return redirect('lista_rubros')
    return render(request, 'proveedores/rubro_eliminar_confirm.html', {'rubro': rubro})


def buscar_proveedor(request):
    """Vista legacy: redirige a la lista unificada preservando querystring."""
    params = request.GET.urlencode()
    url = f"/proveedores/lista/"
    if params:
        url = f"{url}?{params}"
    return redirect(url)
