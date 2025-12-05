# productos/views.py
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.urls import reverse
from .models import Producto, CategoriaProducto, TipoProducto, UnidadMedida
from .forms import (
    ProductoForm,
    CategoriaProductoForm,
    TipoProductoForm,
    UnidadMedidaForm,
)
from pedidos.models import Pedido
from pedidos.services import calcular_consumo_producto, verificar_stock_consumo
from configuracion.permissions import require_perm


# Listar productos
@require_perm('Productos', 'Listar', redirect_to='lista_productos')
def lista_productos(request):
    """Listado de productos con búsqueda, orden y paginación (alineado con otros módulos)."""
    query = request.GET.get('q', '') or request.GET.get('criterio', '')
    order_by = request.GET.get('order_by', 'idProducto')
    direction = request.GET.get('direction', 'asc')

    valid_order_fields = [
        'idProducto', 'nombreProducto', 'precioUnitario',
        'categoriaProducto__nombreCategoria', 'tipoProducto__nombreTipoProducto', 'unidadMedida__nombreUnidad',
    ]
    if order_by not in valid_order_fields:
        order_by = 'idProducto'

    qs = Producto.objects.select_related('categoriaProducto', 'tipoProducto', 'unidadMedida').all()

    if query:
        from django.db.models import Q
        qs = qs.filter(
            Q(nombreProducto__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(categoriaProducto__nombreCategoria__icontains=query) |
            Q(tipoProducto__nombreTipoProducto__icontains=query) |
            Q(unidadMedida__nombreUnidad__icontains=query)
        )

    order_field = f'-{order_by}' if direction == 'desc' else order_by
    qs = qs.order_by(order_field)

    from configuracion.services import get_page_size
    paginator = Paginator(qs, get_page_size())
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'productos': page_obj,
        'query': query,
        'order_by': order_by,
        'direction': direction,
    }
    return render(request, 'productos/lista_productos.html', context)

# Crear producto


@require_perm('Productos', 'Crear', redirect_to='lista_productos')
def crear_producto(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto registrado exitosamente.')
            return redirect('lista_productos')
    else:
        form = ProductoForm()
    return render(request, 'productos/crear_producto.html', {'form': form})

# Editar producto


@require_perm('Productos', 'Editar', redirect_to='lista_productos')
def editar_producto(request, idProducto):
    producto = get_object_or_404(Producto, idProducto=idProducto)
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto modificado exitosamente.')
            return redirect('lista_productos')
    else:
        form = ProductoForm(instance=producto)
    return render(request, 'productos/editar_producto.html', {'form': form})

# Eliminar producto


@require_perm('Productos', 'Eliminar', redirect_to='lista_productos')
def eliminar_producto(request, idProducto):
    producto = get_object_or_404(Producto, idProducto=idProducto)
    if request.method == 'POST':
        # Validar que no esté asociado a pedidos (consideramos cualquier pedido como bloqueo)
        if Pedido.objects.filter(producto=producto).exists():
            messages.error(request, 'No se puede eliminar: el producto está asociado a pedidos.')
            return redirect('lista_productos')
        producto.delete()
        messages.success(request, 'Producto eliminado exitosamente.')
        return redirect('lista_productos')
    return render(request, 'productos/eliminar_producto.html', {'producto': producto})

# Ver detalles del producto


@require_perm('Productos', 'Ver', redirect_to='lista_productos')
def detalle_producto(request, idProducto):
    producto = get_object_or_404(Producto, idProducto=idProducto)
    return render(request, 'productos/detalle_producto.html', {'producto': producto})


@require_perm('Productos', 'Activar', redirect_to='lista_productos')
def activar_producto(request, idProducto):
    """Activar/Desactivar producto (toggle de estado lógico)."""
    producto = get_object_or_404(Producto, idProducto=idProducto)
    if request.method == 'POST':
        producto.activo = not producto.activo
        producto.save(update_fields=['activo'])
        estado = 'activado' if producto.activo else 'desactivado'
        messages.success(request, f'El producto "{producto.nombreProducto}" ha sido {estado}.')
        return redirect('lista_productos')
    return redirect('lista_productos')


# =============================
# CRUD Catálogos (desde Alta)
# =============================

# Categorías
@xframe_options_sameorigin
def lista_categorias(request):
    categorias = CategoriaProducto.objects.all().order_by('nombreCategoria')
    return render(request, 'productos/categorias_lista.html', {'categorias': categorias})


@xframe_options_sameorigin
def crear_categoria(request):
    if request.method == 'POST':
        form = CategoriaProductoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría creada correctamente.')
            url = reverse('lista_categorias')
            if request.GET.get('popup') or request.POST.get('popup'):
                url += '?popup=1'
            return redirect(url)
    else:
        form = CategoriaProductoForm()
    return render(request, 'productos/categoria_form.html', {'form': form, 'modo': 'crear'})


@xframe_options_sameorigin
def editar_categoria(request, pk):
    categoria = get_object_or_404(CategoriaProducto, pk=pk)
    if request.method == 'POST':
        form = CategoriaProductoForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría actualizada correctamente.')
            url = reverse('lista_categorias')
            if request.GET.get('popup') or request.POST.get('popup'):
                url += '?popup=1'
            return redirect(url)
    else:
        form = CategoriaProductoForm(instance=categoria)
    return render(request, 'productos/categoria_form.html', {'form': form, 'modo': 'editar'})


@xframe_options_sameorigin
def eliminar_categoria(request, pk):
    categoria = get_object_or_404(CategoriaProducto, pk=pk)
    if request.method == 'POST':
        categoria.delete()
        messages.success(request, 'Categoría eliminada correctamente.')
        url = reverse('lista_categorias')
        if request.GET.get('popup') or request.POST.get('popup'):
            url += '?popup=1'
        return redirect(url)
    return render(request, 'productos/confirmar_eliminacion_lookup.html', {
        'obj': categoria,
        'tipo': 'Categoría',
        'volver': 'lista_categorias'
    })

# Tipos


@xframe_options_sameorigin
def lista_tipos(request):
    tipos = TipoProducto.objects.all().order_by('nombreTipoProducto')
    return render(request, 'productos/tipos_lista.html', {'tipos': tipos})


@xframe_options_sameorigin
def crear_tipo(request):
    if request.method == 'POST':
        form = TipoProductoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tipo creado correctamente.')
            url = reverse('lista_tipos')
            if request.GET.get('popup') or request.POST.get('popup'):
                url += '?popup=1'
            return redirect(url)
    else:
        form = TipoProductoForm()
    return render(request, 'productos/tipo_form.html', {'form': form, 'modo': 'crear'})


@xframe_options_sameorigin
def editar_tipo(request, pk):
    tipo = get_object_or_404(TipoProducto, pk=pk)
    if request.method == 'POST':
        form = TipoProductoForm(request.POST, instance=tipo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tipo actualizado correctamente.')
            url = reverse('lista_tipos')
            if request.GET.get('popup') or request.POST.get('popup'):
                url += '?popup=1'
            return redirect(url)
    else:
        form = TipoProductoForm(instance=tipo)
    return render(request, 'productos/tipo_form.html', {'form': form, 'modo': 'editar'})


@xframe_options_sameorigin
def eliminar_tipo(request, pk):
    tipo = get_object_or_404(TipoProducto, pk=pk)
    if request.method == 'POST':
        tipo.delete()
        messages.success(request, 'Tipo eliminado correctamente.')
        url = reverse('lista_tipos')
        if request.GET.get('popup') or request.POST.get('popup'):
            url += '?popup=1'
        return redirect(url)
    return render(request, 'productos/confirmar_eliminacion_lookup.html', {
        'obj': tipo,
        'tipo': 'Tipo',
        'volver': 'lista_tipos'
    })

# Unidades de medida


@xframe_options_sameorigin
def lista_unidades(request):
    unidades = UnidadMedida.objects.all().order_by('nombreUnidad')
    return render(request, 'productos/unidades_lista.html', {'unidades': unidades})


@xframe_options_sameorigin
def crear_unidad(request):
    if request.method == 'POST':
        form = UnidadMedidaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Unidad creada correctamente.')
            url = reverse('lista_unidades')
            if request.GET.get('popup') or request.POST.get('popup'):
                url += '?popup=1'
            return redirect(url)
    else:
        form = UnidadMedidaForm()
    return render(request, 'productos/unidad_form.html', {'form': form, 'modo': 'crear'})


@xframe_options_sameorigin
def editar_unidad(request, pk):
    unidad = get_object_or_404(UnidadMedida, pk=pk)
    if request.method == 'POST':
        form = UnidadMedidaForm(request.POST, instance=unidad)
        if form.is_valid():
            form.save()
            messages.success(request, 'Unidad actualizada correctamente.')
            url = reverse('lista_unidades')
            if request.GET.get('popup') or request.POST.get('popup'):
                url += '?popup=1'
            return redirect(url)
    else:
        form = UnidadMedidaForm(instance=unidad)
    return render(request, 'productos/unidad_form.html', {'form': form, 'modo': 'editar'})


@xframe_options_sameorigin
def eliminar_unidad(request, pk):
    unidad = get_object_or_404(UnidadMedida, pk=pk)
    if request.method == 'POST':
        unidad.delete()
        messages.success(request, 'Unidad eliminada correctamente.')
        url = reverse('lista_unidades')
        if request.GET.get('popup') or request.POST.get('popup'):
            url += '?popup=1'
        return redirect(url)
    return render(request, 'productos/confirmar_eliminacion_lookup.html', {
        'obj': unidad,
        'tipo': 'Unidad de Medida',
        'volver': 'lista_unidades'
    })


def calcular_consumo(request, producto_id: int, cantidad: int):
    """Devuelve el consumo de insumos para un producto y cantidad usando la receta.
    Respuesta JSON: { success, producto: str, cantidad: int, consumo: [{codigo, nombre, requerido, stock, faltan}] }
    """
    try:
        producto = get_object_or_404(Producto, pk=producto_id)
        consumo_dict = calcular_consumo_producto(producto, int(cantidad))

        # Enriquecer con datos de insumo
        from insumos.models import Insumo
        insumos = {i.idInsumo: i for i in Insumo.objects.filter(idInsumo__in=consumo_dict.keys())}
        detalle = []
        for iid, req in consumo_dict.items():
            ins = insumos.get(iid)
            if not ins:
                continue
            stock = float(ins.stock)
            faltan = max(0.0, float(req) - stock)
            detalle.append({
                'codigo': ins.codigo,
                'nombre': ins.nombre,
                'requerido': float(req),
                'stock': stock,
                'faltan': faltan,
            })

        ok, faltantes = verificar_stock_consumo(consumo_dict)
        return JsonResponse({
            'success': True,
            'producto': producto.nombreProducto,
            'cantidad': int(cantidad),
            'ok': ok,
            'consumo': detalle,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
