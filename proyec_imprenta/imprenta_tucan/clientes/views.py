from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib import messages
from .models import Cliente
from .forms import ClienteForm

# Alta de cliente


def alta_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            messages.success(request, f'El cliente {cliente.nombre} {cliente.apellido} ha sido creado exitosamente.')
            return redirect('lista_clientes')
        else:
            # Los errores del formulario se mostrarán automáticamente en el template
            messages.error(request, 'Por favor corrija los errores en el formulario.')
    else:
        form = ClienteForm()
    return render(request, 'clientes/alta.html', {'form': form})

# Lista de clientes unificada con búsqueda y ordenamiento (reemplaza "buscar")


def lista_clientes(request):
    # Parámetros unificados: usamos 'q' para búsqueda; mantenemos 'criterio' como alias por compatibilidad
    query = request.GET.get('q', '') or request.GET.get('criterio', '')
    order_by = request.GET.get('order_by', 'apellido')
    direction = request.GET.get('direction', 'asc')

    # Campos de orden válidos
    valid_order_fields = ['id', 'nombre', 'apellido', 'email', 'telefono', 'direccion']
    if order_by not in valid_order_fields:
        order_by = 'apellido'

    clientes_qs = Cliente.objects.all()
    if query:
        if order_by == 'id' and query.isdigit():
            clientes_qs = clientes_qs.filter(id=int(query))
        else:
            clientes_qs = clientes_qs.filter(
                Q(nombre__icontains=query) |
                Q(apellido__icontains=query) |
                Q(razon_social__icontains=query) |
                Q(email__icontains=query) |
                Q(telefono__icontains=query) |
                Q(direccion__icontains=query)
            )

    # Orden
    order_field = f'-{order_by}' if direction == 'desc' else order_by
    clientes_qs = clientes_qs.order_by(order_field)

    # Paginación
    from configuracion.services import get_page_size
    paginator = Paginator(clientes_qs, get_page_size())
    page = request.GET.get('page')
    clientes = paginator.get_page(page)

    return render(request, 'clientes/lista_clientes.html', {
        'clientes': clientes,
        'query': query,
        'order_by': order_by,
        'direction': direction,
    })

# Detalle de cliente


def detalle_cliente(request, id):
    cliente = get_object_or_404(Cliente, id=id)
    return render(request, 'clientes/detalle_cliente.html', {'cliente': cliente})

# Editar cliente


def editar_cliente(request, id):
    cliente = get_object_or_404(Cliente, id=id)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            cliente_actualizado = form.save()
            messages.success(
                request, f'El cliente {cliente_actualizado.nombre} {cliente_actualizado.apellido} ha sido actualizado exitosamente.')
            return redirect('lista_clientes')
        else:
            messages.error(request, 'Por favor corrija los errores en el formulario.')
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'clientes/editar_cliente.html', {'form': form, 'cliente': cliente})

# Eliminar cliente


def eliminar_cliente(request, id):
    cliente = get_object_or_404(Cliente, id=id)
    if request.method == 'POST':
        nombre_cliente = f"{cliente.nombre} {cliente.apellido}"
        cliente.delete()
        messages.success(request, f'El cliente {nombre_cliente} ha sido eliminado exitosamente.')
        return redirect('lista_clientes')
    return redirect('lista_clientes')


# Activar/desactivar cliente (toggle)
def activar_cliente(request, id):
    cliente = get_object_or_404(Cliente, id=id)
    if request.method == 'POST':
        cliente.estado = 'Inactivo' if cliente.estado == 'Activo' else 'Activo'
        cliente.save()
        estado_txt = 'activado' if cliente.estado == 'Activo' else 'desactivado'
        messages.success(request, f'El cliente {cliente.nombre} {cliente.apellido} ha sido {estado_txt}.')
    return redirect('lista_clientes')


# Buscar cliente
def buscar_cliente(request):
    """Vista legacy: redirige a la lista unificada preservando querystring."""
    params = request.GET.urlencode()
    url = f"/clientes/lista/"
    if params:
        url = f"{url}?{params}"
    return redirect(url)

# Confirmar eliminación de cliente


def confirmar_eliminacion_cliente(request, id):
    cliente = get_object_or_404(Cliente, id=id)

    if request.method == 'POST':
        cliente.delete()
        messages.success(request, 'El cliente ha sido eliminado exitosamente.')
        return redirect('lista_clientes')

    return render(request, 'clientes/confirmar_eliminacion.html', {'cliente': cliente})


def activar_cliente(request, id):
    """Activar/desactivar cliente para igualar funcionalidad de proveedores"""
    cliente = get_object_or_404(Cliente, id=id)

    if request.method == 'POST':
        cliente.estado = 'Inactivo' if cliente.estado == 'Activo' else 'Activo'
        cliente.save()
        estado = 'activado' if cliente.estado == 'Activo' else 'desactivado'
        messages.success(request, f'El cliente {cliente.nombre} {cliente.apellido} ha sido {estado}.')
        return redirect('lista_clientes')

    return redirect('lista_clientes')
