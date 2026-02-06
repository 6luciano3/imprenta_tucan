from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from .models import RecetaProducto
from .forms import FormulaForm
from django.shortcuts import render, redirect, get_object_or_404
from .utils.safe_eval import safe_eval
import json
from django.shortcuts import redirect, get_object_or_404
from .models import Parametro, GrupoParametro, Formula, FormulaHistorial
from .services import UnidadDeMedidaRepository
from .forms import UnidadDeMedidaForm
from .models import UnidadDeMedida
from django.shortcuts import render
from .forms import RecetaProductoForm
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .permissions import require_perm
# AJAX: actualizar solo la fórmula de una receta


@login_required
@require_perm('Recetas', 'Editar')
@require_POST
def receta_producto_update_formula(request, pk):
    from .models import Formula
    receta = get_object_or_404(RecetaProducto, pk=pk)
    formula_id = request.POST.get('formula_id')
    if not formula_id:
        return JsonResponse({'ok': False, 'error': 'Fórmula no especificada'}, status=400)
    try:
        formula = Formula.objects.get(pk=formula_id)
    except Formula.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Fórmula no encontrada'}, status=404)
    receta.producto.formula = formula
    receta.producto.save()
    return JsonResponse({'ok': True, 'formula': str(formula)})


def configuracion_home(request):
    return render(request, 'configuracion/dashboard.html')


def redirect_configuracion(request):
    return redirect('lista_formulas')


def unidad_list(request):
    unidades = UnidadDeMedidaRepository.get_all()
    return render(request, 'configuracion/unidad_list.html', {'unidades': unidades})


def unidad_create(request):
    if request.method == 'POST':
        form = UnidadDeMedidaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('unidad_list')
    else:
        form = UnidadDeMedidaForm()
    return render(request, 'configuracion/unidad_form.html', {'form': form})


def unidad_update(request, pk):
    unidad = get_object_or_404(UnidadDeMedida, pk=pk)
    if request.method == 'POST':
        form = UnidadDeMedidaForm(request.POST, instance=unidad)
        if form.is_valid():
            form.save()
            return redirect('unidad_list')
    else:
        form = UnidadDeMedidaForm(instance=unidad)
    return render(request, 'configuracion/unidad_form.html', {'form': form})


def lista_configuracion(request):
    parametros = Parametro.objects.all().order_by('id')[:100]
    grupos = GrupoParametro.objects.all()
    formulas = Formula.objects.all().order_by('-actualizado_en')
    total_formulas = formulas.count()
    activas = formulas.filter(activo=True).count()
    inactivas = formulas.filter(activo=False).count()
    ultima_actualizacion = formulas.first().actualizado_en if formulas.exists() else None
    return render(request, 'configuracion/lista_configuracion.html', {
        'parametros': parametros,
        'grupos': grupos,
        'formulas': formulas,
        'total_formulas': total_formulas,
        'formulas_activas': activas,
        'formulas_inactivas': inactivas,
        'ultima_actualizacion': ultima_actualizacion,
    })


def lista_formulas(request):
    from django.core.paginator import Paginator
    from django.db.models import Q

    query = request.GET.get('q', '').strip()
    order_by = request.GET.get('order_by', 'insumo')
    direction = request.GET.get('direction', 'asc')

    formulas_qs = Formula.objects.select_related('insumo').all()
    if query:
        formulas_qs = formulas_qs.filter(
            Q(codigo__icontains=query) |
            Q(insumo__nombre__icontains=query) |
            Q(expresion__icontains=query)
        )

    # Map order_by to model fields
    order_map = {
        'codigo': 'codigo',
        'insumo': 'insumo__nombre',
        'version': 'version',
        'activo': 'activo',
    }
    order_field = order_map.get(order_by, 'insumo__nombre')
    if direction == 'desc':
        order_field = '-' + order_field
    formulas_qs = formulas_qs.order_by(order_field, 'codigo')

    paginator = Paginator(formulas_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'formulas': page_obj,
        'page_obj': page_obj,
        'query': query,
        'order_by': order_by,
        'direction': direction,
    }
    return render(request, 'configuracion/lista_formulas.html', context)


@login_required
@require_perm('Formulas', 'Crear')
def crear_formula(request):
    if request.method == 'POST':
        form = FormulaForm(request.POST)
        if form.is_valid():
            formula = form.save(commit=False)
            formula.version = 1
            formula.save()
            FormulaHistorial.objects.create(
                formula=formula,
                version=formula.version,
                expresion=formula.expresion,
                usuario=request.user
            )
            return redirect('lista_formulas')
    else:
        form = FormulaForm()
    return render(request, 'configuracion/formula_form.html', {'form': form})


@login_required
@require_perm('Formulas', 'Editar')
def editar_formula(request, pk):
    formula = get_object_or_404(Formula, pk=pk)
    if request.method == 'POST':
        form = FormulaForm(request.POST, instance=formula)
        if form.is_valid():
            old_version = formula.version
            old_expr = formula.expresion
            formula = form.save(commit=False)
            formula.version += 1
            formula.save()
            FormulaHistorial.objects.create(
                formula=formula,
                version=old_version,
                expresion=old_expr,
                usuario=request.user
            )
            return redirect('lista_formulas')
    else:
        form = FormulaForm(instance=formula)
    return render(request, 'configuracion/formula_form.html', {'form': form, 'formula': formula})


@require_POST
def validar_formula(request):
    data = json.loads(request.body)
    expr = data.get('expresion')
    variables = data.get('variables', {})
    try:
        res = safe_eval(expr, variables)
        return JsonResponse({'ok': True, 'resultado': res})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@require_perm('Formulas', 'Editar')
@require_POST
def activar_formula(request, pk):
    formula = get_object_or_404(Formula, pk=pk)
    if not formula.activo:
        formula.activo = True
        formula.save()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/configuracion/formulas/'))


@login_required
@require_perm('Formulas', 'Editar')
@require_POST
def desactivar_formula(request, pk):
    formula = get_object_or_404(Formula, pk=pk)
    if formula.activo:
        formula.activo = False
        formula.save()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/configuracion/formulas/'))

# --- CRUD RecetaProducto ---


@login_required
@require_perm('Recetas', 'Ver')
def receta_producto_list(request):
    # Parámetros de búsqueda y orden
    from django.db.models import Q
    query = request.GET.get('q', '').strip()
    order_by = request.GET.get('order_by', 'actualizado')
    direction = request.GET.get('direction', 'desc')

    # Base queryset
    qs = RecetaProducto.objects.select_related('producto').prefetch_related('insumos').all()

    # Filtros de búsqueda (producto, insumo, descripción)
    if query:
        qs = qs.filter(
            Q(producto__nombreProducto__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(insumos__nombre__icontains=query) |
            Q(insumos__codigo__icontains=query)
        ).distinct()

    # Mapa de orden
    order_map = {
        'producto': 'producto__nombreProducto',
        'activo': 'activo',
        'actualizado': 'actualizado_en',
        'creado': 'creado_en',
    }
    order_field = order_map.get(order_by, 'actualizado_en')
    if direction == 'desc':
        order_field = '-' + order_field
    qs = qs.order_by(order_field)

    # Paginación
    from configuracion.services import get_page_size
    from django.core.paginator import Paginator
    paginator = Paginator(qs, get_page_size())
    page = request.GET.get('page')
    recetas = paginator.get_page(page)

    # Fórmulas activas para el modal
    formulas = Formula.objects.filter(activo=True).order_by('nombre')
    import json
    formulas_json = [{'id': f.id, 'nombre': f.nombre} for f in formulas]

    return render(request, 'configuracion/receta_producto_list.html', {
        'recetas': recetas,
        'page_obj': recetas,
        'query': query,
        'order_by': order_by,
        'direction': direction,
        'formulas': formulas,
        'formulas_json': json.dumps(formulas_json, ensure_ascii=False)
    })


@login_required
@require_perm('Recetas', 'Crear')
def receta_producto_create(request):
    if request.method == 'POST':
        form = RecetaProductoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('receta_producto_list')
    else:
        form = RecetaProductoForm()
    return render(request, 'configuracion/receta_producto_form.html', {'form': form})


@login_required
@require_perm('Recetas', 'Editar')
def receta_producto_update(request, pk):
    receta = get_object_or_404(RecetaProducto, pk=pk)
    if request.method == 'POST':
        form = RecetaProductoForm(request.POST, instance=receta)
        if form.is_valid():
            form.save()
            return redirect('receta_producto_list')
    else:
        form = RecetaProductoForm(instance=receta)
    return render(request, 'configuracion/receta_producto_form.html', {'form': form, 'receta': receta})


@login_required
@require_perm('Recetas', 'Eliminar')
def receta_producto_delete(request, pk):
    receta = get_object_or_404(RecetaProducto, pk=pk)
    if request.method == 'POST':
        receta.delete()
        return redirect('receta_producto_list')
    return render(request, 'configuracion/receta_producto_confirm_delete.html', {'receta': receta})


def lista_recetas_productos(request):
    qs = RecetaProducto.objects.select_related('producto').prefetch_related('insumos').all()
    from configuracion.services import get_page_size
    from django.core.paginator import Paginator
    paginator = Paginator(qs, get_page_size())
    page = request.GET.get('page')
    recetas = paginator.get_page(page)

    # Para saber si el producto está en algún pedido (solo los de la página actual)
    productos_con_pedidos = set()
    from pedidos.models import Pedido
    for receta in recetas:
        if Pedido.objects.filter(producto=receta.producto).exists():
            # Compatibilidad según nombre de campo de Producto (id/idProducto)
            prod_id = getattr(receta.producto, 'idProducto', None) or getattr(receta.producto, 'id', None)
            if prod_id is not None:
                productos_con_pedidos.add(prod_id)
    return render(request, 'configuracion/lista_recetas_productos.html', {
        'recetas': recetas,
        'productos_con_pedidos': productos_con_pedidos
    })
