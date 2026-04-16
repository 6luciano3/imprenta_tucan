from django.http import HttpResponseRedirect
from django.contrib import messages
from permisos.decorators import requiere_permiso

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
from .forms import OfertasReglasForm
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


@login_required
@requiere_permiso("Parametrizar el Sistema")
def motor_demanda_config(request):
    """Permite editar los umbrales R1, R2 y R3 del Motor de Demanda."""
    from configuracion.models import Parametro, GrupoParametro
    from core.motor.config import MotorConfig, DEFAULTS

    PARAMS = [
        {
            'clave': 'DEMANDA_UMBRAL_CRITICO',
            'nombre': 'R1 — Umbral stock crítico',
            'descripcion': 'Stock ≤ este valor activa "🔴 Sin stock crítico" (prioridad Alta). Valor 0 = solo se activa cuando el stock llega a cero.',
            'tipo': Parametro.TIPO_INT,
            'step': '1',
            'min': '0',
        },
        {
            'clave': 'STOCK_MINIMO_GLOBAL',
            'nombre': 'R2 — Stock mínimo global',
            'descripcion': 'Stock < este valor activa "🟠 Compra urgente" (prioridad Alta). Se usa como piso cuando no hay historial de consumo registrado.',
            'tipo': Parametro.TIPO_INT,
            'step': '1',
            'min': '0',
        },
        {
            'clave': 'DEMANDA_FACTOR_PREVENTIVO',
            'nombre': 'R3 — Factor demanda preventiva',
            'descripcion': 'Stock < demanda × este factor activa "🟡 Compra preventiva" (prioridad Media). Valor 1.0 = se activa cuando el stock es menor a la demanda proyectada.',
            'tipo': Parametro.TIPO_FLOAT,
            'step': '0.1',
            'min': '0',
        },
    ]

    if request.method == 'POST':
        grupo, _ = GrupoParametro.objects.get_or_create(
            codigo='MOTOR_DEMANDA',
            defaults={'nombre': 'Motor de Demanda'},
        )
        for p in PARAMS:
            raw = request.POST.get(p['clave'], '').strip()
            if raw:
                Parametro.set(p['clave'], raw, tipo=p['tipo'], grupo=grupo, nombre=p['nombre'])
        return redirect(request.path + '?saved=1')

    saved = request.GET.get('saved') == '1'
    params = [
        {**p, 'valor': MotorConfig.get(p['clave']) if MotorConfig.get(p['clave']) is not None else DEFAULTS.get(p['clave'], '')}
        for p in PARAMS
    ]
    return render(request, 'configuracion/motor_demanda.html', {'params': params, 'saved': saved})


@login_required
@requiere_permiso("Parametrizar el Sistema")
def proyeccion_demanda_config(request):
    """Permite editar los parámetros de visualización y ejecución de la Proyección de Demanda."""
    from configuracion.models import Parametro, GrupoParametro
    from core.motor.config import MotorConfig, DEFAULTS

    PARAMS = [
        {
            'clave': 'PROYECCION_N_INSUMOS',
            'nombre': 'Cantidad de insumos a mostrar',
            'descripcion': 'Número de filas que se muestran en la tabla "Proyección Demanda Insumos" del dashboard.',
            'tipo': Parametro.TIPO_INT,
            'step': '1',
            'min': '0',
            'max': '50',
        },
        {
            'clave': 'PROYECCION_MESES',
            'nombre': 'Ventana de meses (media móvil)',
            'descripcion': 'Cantidad de meses hacia atrás usados para la Media Móvil Ponderada. Aplica tanto al dashboard como a la tarea automática.',
            'tipo': Parametro.TIPO_INT,
            'step': '1',
            'min': '1',
        },
        {
            'clave': 'TOP_N_PROVEEDORES_COTIZACION',
            'nombre': 'Top N proveedores para SC automática',
            'descripcion': 'Cantidad de proveedores rankeados que reciben la Solicitud de Cotización automáticamente al generar proyecciones.',
            'tipo': Parametro.TIPO_INT,
            'step': '1',
            'min': '1',
            'max': '10',
        },
        {
            'clave': 'PROYECCION_MESES_ETS',
            'nombre': 'Períodos históricos para método ETS',
            'descripcion': 'Cantidad de meses de historial usados por el modelo de suavizamiento exponencial (ETS). Más meses = proyección más estable pero más lenta de reaccionar.',
            'tipo': Parametro.TIPO_INT,
            'step': '1',
            'min': '3',
            'max': '24',
        },
    ]

    ALGORITMO_OPCIONES = [
        ('media_movil', 'Media Móvil Ponderada', 'Promedio de los últimos N meses con mayor peso en meses recientes. Reacciona rápido a cambios.'),
        ('ets', 'Suavizado Exponencial (ETS)', 'Suaviza el historial dando mayor peso a observaciones recientes con un factor alpha configurable. Más estable ante fluctuaciones.'),
    ]

    # Parámetros informativos (no se pueden cambiar desde aquí — el crontab es fijo en settings)
    INFO_SCHEDULE = {
        'crontab_fijo': 'Cada hora (configurado en settings.py)',
        'tarea': 'automatizacion.tasks.tarea_prediccion_demanda',
    }

    if request.method == 'POST':
        # Botón "Ejecutar ahora"
        if 'ejecutar_ahora' in request.POST:
            from insumos.tasks import generar_proyecciones_insumos
            try:
                generar_proyecciones_insumos.delay()
                messages.success(request, 'Tarea enviada a la cola Celery. Los resultados estarán disponibles en unos segundos.')
            except Exception:
                # Celery/Redis no disponible — ejecutar sincrónicamente
                try:
                    generar_proyecciones_insumos()
                    messages.success(request, 'Proyecciones generadas correctamente (ejecución directa, Celery no disponible).')
                except Exception as e:
                    messages.error(request, f'Error al ejecutar la tarea: {e}')
            return redirect(request.path)

        grupo, _ = GrupoParametro.objects.get_or_create(
            codigo='PROYECCION_DEMANDA',
            defaults={'nombre': 'Proyección Demanda'},
        )

        # Guardar algoritmo seleccionado
        algoritmo_elegido = request.POST.get('ALGORITMO_PROYECCION', 'media_movil')
        if algoritmo_elegido in ('media_movil', 'ets'):
            Parametro.set('ALGORITMO_PROYECCION', algoritmo_elegido, tipo=Parametro.TIPO_CADENA,
                          grupo=grupo, nombre='Algoritmo de proyección')

        errores = []
        for p in PARAMS:
            raw = request.POST.get(p['clave'], '').strip()
            if not raw:
                continue
            
            # Para PROYECCION_N_INSUMOS: solo permitir 0-50
            if p['clave'] == 'PROYECCION_N_INSUMOS':
                # Validar que sea número positivo
                if not raw.isdigit():
                    errores.append(f"{p['nombre']}: debe ser un número entre 0 y 50.")
                    continue
                val = int(raw)
                if not (0 <= val <= 50):
                    errores.append(f"{p['nombre']}: debe estar entre 0 y 50.")
                    continue
                Parametro.set(p['clave'], str(val), tipo=p['tipo'], grupo=grupo, nombre=p['nombre'])
                continue
            
            # Para los otros parámetros: validación original
            import re
            if not re.match(r'^-?\d+$', raw):
                errores.append(f"{p['nombre']}: debe ser un número entero.")
                continue
            if len(raw) > 10:
                errores.append(f"{p['nombre']}: valor demasiado largo.")
                continue
            try:
                val = int(raw)
                min_val = int(p.get('min', 0))
                max_val = int(p.get('max', 9999))
                if not (min_val <= val <= max_val):
                    errores.append(f"{p['nombre']}: debe estar entre {min_val} y {max_val}.")
                    continue
            except ValueError:
                errores.append(f"{p['nombre']}: debe ser un número entero.")
                continue
            Parametro.set(p['clave'], str(val), tipo=p['tipo'], grupo=grupo, nombre=p['nombre'])
        if errores:
            for e in errores:
                messages.error(request, e)
            return redirect(request.path)
        return redirect(request.path + '?saved=1')

    saved = request.GET.get('saved') == '1'
    params = [
        {**p, 'valor': MotorConfig.get(p['clave']) if MotorConfig.get(p['clave']) is not None else DEFAULTS.get(p['clave'], '')}
        for p in PARAMS
    ]

    # Algoritmo actualmente seleccionado
    algoritmo_actual = str(MotorConfig.get('ALGORITMO_PROYECCION') or 'media_movil').strip()

    # Resumen del estado actual de proyecciones
    from insumos.models import ProyeccionInsumo
    from django.utils import timezone
    periodo_actual = timezone.now().strftime('%Y-%m')
    total_proyecciones = ProyeccionInsumo.objects.filter(periodo=periodo_actual).count()
    pendientes = ProyeccionInsumo.objects.filter(periodo=periodo_actual, estado='pendiente').count()
    ultima = ProyeccionInsumo.objects.filter(periodo=periodo_actual).order_by('-fecha_generacion').first()

    return render(request, 'configuracion/proyeccion_demanda.html', {
        'params': params,
        'saved': saved,
        'info_schedule': INFO_SCHEDULE,
        'algoritmo_actual': algoritmo_actual,
        'algoritmo_opciones': ALGORITMO_OPCIONES,
        'estado_proyecciones': {
            'periodo': periodo_actual,
            'total': total_proyecciones,
            'pendientes': pendientes,
            'ultima_generacion': ultima.fecha_generacion if ultima else None,
        },
    })


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


@login_required
def lista_formulas(request):
    from django.core.paginator import Paginator
    from django.db.models import Q

    query = request.GET.get('q', '').strip()
    order_by = request.GET.get('order_by', 'insumo')
    direction = request.GET.get('direction', 'asc')

    formulas_qs = Formula.objects.select_related('insumo').filter(insumo__tipo='directo')
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

    from configuracion.services import get_page_size
    paginator = Paginator(formulas_qs, get_page_size())
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
            # Guardar el estado anterior en historial ANTES de modificar
            FormulaHistorial.objects.create(
                formula=formula,
                version=formula.version,
                expresion=formula.expresion,
                usuario=request.user
            )
            formula = form.save(commit=False)
            formula.version += 1
            formula.save()
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

    return render(request, 'configuracion/receta_producto_list.html', {
        'recetas': recetas,
        'page_obj': recetas,
        'query': query,
        'order_by': order_by,
        'direction': direction,
        'formulas': formulas,
    })


def _sync_bom_desde_receta_config(receta):
    """Sincroniza ProductoInsumo (BOM) a partir del M2M de RecetaProducto.
    - Crea entradas faltantes con cantidad_por_unidad=1 (no sobreescribe cantidades existentes).
    - Elimina entradas del BOM cuyos insumos ya no están en la config.
    """
    from productos.models import ProductoInsumo
    producto = receta.producto
    insumos_config = set(receta.insumos.values_list('idInsumo', flat=True))

    # Agregar insumos nuevos con cantidad por defecto
    for insumo_id in insumos_config:
        ProductoInsumo.objects.get_or_create(
            producto=producto,
            insumo_id=insumo_id,
            defaults={'cantidad_por_unidad': 1, 'es_costo_fijo': False},
        )

    # Eliminar insumos que ya no están en la config
    ProductoInsumo.objects.filter(producto=producto).exclude(insumo_id__in=insumos_config).delete()


@login_required
@require_perm('Recetas', 'Crear')
def receta_producto_create(request):
    next_url = request.GET.get('next', '')
    if request.method == 'POST':
        form = RecetaProductoForm(request.POST)
        if form.is_valid():
            receta = form.save()
            _sync_bom_desde_receta_config(receta)
            if next_url:
                return redirect(next_url)
            return redirect('gestionar_receta', idProducto=receta.producto.idProducto)
    else:
        form = RecetaProductoForm()
    return render(request, 'configuracion/receta_producto_form.html', {'form': form, 'next': next_url})


@login_required
@require_perm('Recetas', 'Editar')
def receta_producto_update(request, pk):
    receta = get_object_or_404(RecetaProducto, pk=pk)
    next_url = request.GET.get('next', '')
    if request.method == 'POST':
        form = RecetaProductoForm(request.POST, instance=receta)
        if form.is_valid():
            receta = form.save()
            _sync_bom_desde_receta_config(receta)
            if next_url:
                return redirect(next_url)
            return redirect('gestionar_receta', idProducto=receta.producto.idProducto)
    else:
        form = RecetaProductoForm(instance=receta)
    return render(request, 'configuracion/receta_producto_form.html', {'form': form, 'receta': receta, 'next': next_url})


@login_required
@require_perm('Recetas', 'Eliminar')
def receta_producto_delete(request, pk):
    receta = get_object_or_404(RecetaProducto, pk=pk)
    if request.method == 'POST':
        receta.delete()
        return redirect('receta_producto_list')
    return render(request, 'configuracion/receta_producto_confirm_delete.html', {'receta': receta})


@login_required
@require_perm('Recetas', 'Editar')
def sync_bom_one(request, pk):
    """Sincroniza el BOM (ProductoInsumo) de una sola RecetaProducto."""
    receta = get_object_or_404(RecetaProducto, pk=pk)
    _sync_bom_desde_receta_config(receta)
    messages.success(request, f'BOM de "{receta.producto.nombreProducto}" sincronizado correctamente.')
    return redirect('receta_producto_list')


@login_required
@require_perm('Recetas', 'Editar')
def sync_bom_all(request):
    """Sincroniza el BOM de TODAS las RecetaProducto existentes."""
    if request.method != 'POST':
        return redirect('receta_producto_list')
    recetas = RecetaProducto.objects.prefetch_related('insumos').select_related('producto')
    count = 0
    for receta in recetas:
        _sync_bom_desde_receta_config(receta)
        count += 1
    messages.success(request, f'BOM sincronizado para {count} receta(s). Los "Insumos Requeridos" ahora coinciden con Configuración.')
    return redirect('receta_producto_list')


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


# --- UI rápida para editar reglas de ofertas (sin Admin) ---
@login_required
@requiere_permiso("Parametrizar el Sistema")
def editar_reglas_ofertas(request):
    # Permitir a staff o grupo "Comercial"
    es_staff = getattr(request.user, 'is_staff', False)
    pertenece_comercial = request.user.groups.filter(name='Comercial').exists()
    if not (es_staff or pertenece_comercial):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("No tienes permisos para editar reglas de ofertas.")

    # Cargar reglas actuales (o por defecto)
    default_rules = [
        {
            'nombre': 'Descuento por alto desempeño',
            'condiciones': {'score_gte': 80},
            'accion': {
                'tipo': 'descuento',
                'titulo': 'Descuento por alto desempeño',
                'descripcion': 'Descuento del 10% en el próximo pedido.',
                'parametros': {'descuento': 10}
            }
        },
        {
            'nombre': 'Fidelización por caída',
            'condiciones': {'decline_periods_gte': 2, 'decline_delta_lte': -10},
            'accion': {
                'tipo': 'fidelizacion',
                'titulo': 'Oferta de fidelización',
                'descripcion': 'Condiciones de pago mejoradas (30 días sin intereses).',
                'parametros': {'dias_sin_interes': 30}
            }
        },
        {
            'nombre': 'Prioridad por criticidad',
            'condiciones': {'crit_norm_gte': 0.7},
            'accion': {
                'tipo': 'prioridad_stock',
                'titulo': 'Beneficio por consumo crítico',
                'descripcion': 'Prioridad en stock para insumos críticos.',
                'parametros': {'prioridad': 'alta'}
            }
        },
        {
            'nombre': 'Promoción por buen margen',
            'condiciones': {'margen_norm_gte': 0.6},
            'accion': {
                'tipo': 'promocion',
                'titulo': 'Promoción especial',
                'descripcion': 'Bonificación en servicios complementarios en el próximo pedido.',
                'parametros': {'bonificacion': 'servicio_complementario'}
            }
        }
    ]

    import json
    reglas_actuales = Parametro.get('OFERTAS_REGLAS_JSON', default_rules)
    initial_text = json.dumps(reglas_actuales, ensure_ascii=False, indent=2)

    saved = False
    if request.method == 'POST':
        form = OfertasReglasForm(request.POST)
        if form.is_valid():
            raw = form.cleaned_data['reglas_json']
            data = json.loads(raw)
            # Asegurar grupo "AUTOMATIZACION" para este parámetro
            grupo, _ = GrupoParametro.objects.get_or_create(
                codigo='AUTOMATIZACION',
                defaults={'nombre': 'Automatización', 'descripcion': 'Parámetros de automatización y ofertas'}
            )
            Parametro.set(
                'OFERTAS_REGLAS_JSON',
                data,
                tipo=Parametro.TIPO_JSON,
                grupo=grupo,
                nombre='Reglas de Ofertas (JSON)',
                descripcion='Reglas parametrizables para generación de ofertas',
            )
            saved = True
            initial_text = json.dumps(data, ensure_ascii=False, indent=2)
        else:
            # Mantener texto ingresado si hay error
            initial_text = request.POST.get('reglas_json', initial_text)
    else:
        form = OfertasReglasForm(initial={'reglas_json': initial_text})

    context = {
        'form': form,
        'saved': saved,
        'reglas_actuales': reglas_actuales,
    }
    return render(request, 'configuracion/ofertas_reglas.html', context)


def empresa_config(request):
    from .models import Parametro, GrupoParametro
    CAMPOS = [
        ('EMPRESA_RAZON_SOCIAL',   'Razón Social'),
        ('EMPRESA_CUIT',           'CUIT'),
        ('EMPRESA_DOMICILIO',      'Domicilio'),
        ('EMPRESA_TELEFONO',       'Teléfono'),
        ('EMPRESA_EMAIL',          'Email interno'),
        ('EMPRESA_EMAIL_CONTACTO', 'Email público de contacto'),
        ('EMPRESA_CONDICION_IVA',  'Condición ante IVA'),
    ]
    if request.method == 'POST':
        grupo, _ = GrupoParametro.objects.get_or_create(
            codigo='EMPRESA',
            defaults={'nombre': 'Datos de la Empresa'}
        )
        for codigo, nombre in CAMPOS:
            valor = request.POST.get(codigo, '').strip()
            if valor:
                obj, created = Parametro.objects.get_or_create(
                    codigo=codigo,
                    defaults={'valor': valor, 'nombre': nombre, 'tipo': 'str', 'grupo': grupo}
                )
                if not created:
                    obj.valor = valor
                    obj.save()
        from django.contrib import messages
        messages.success(request, 'Datos de la empresa actualizados correctamente.')
        from django.shortcuts import redirect
        return redirect('empresa_config')

    # Pasar lista de (codigo, nombre, valor) para evitar lookup de dict en template
    campos_con_valor = [
        (codigo, nombre, Parametro.get(codigo, ''))
        for codigo, nombre in CAMPOS
    ]
    from django.shortcuts import render
    return render(request, 'configuracion/empresa_config.html', {
        'campos_con_valor': campos_con_valor
    })


@login_required
@requiere_permiso("Parametrizar el Sistema")
def ofertas_segmentadas_config(request):
    """Permite editar los parámetros de cada tier de Ofertas Segmentadas (PI-1)."""
    from configuracion.models import Parametro, GrupoParametro

    # Definición de los 4 tiers y sus campos editables
    TIERS = [
        {
            'clave_base': 'OFERTA_TIER_PREMIUM',
            'nombre': 'Premium',
            'color': 'yellow',
            'icono': 'workspace_premium',
            'tiene_score_min': True,
            'score_min_label': 'Score mínimo',
            'score_min_desc': 'Clientes con score ≥ este valor son clasificados como Premium.',
            'score_min_default': 90,
            'descuento_default': 15,
            'titulo_default': 'Combo Premium',
            'descripcion_default': 'Descuento exclusivo del 15% por ser nuestro cliente de mayor valor.',
        },
        {
            'clave_base': 'OFERTA_TIER_ESTRATEGICO',
            'nombre': 'Estratégico',
            'color': 'blue',
            'icono': 'stars',
            'tiene_score_min': True,
            'score_min_label': 'Score mínimo',
            'score_min_desc': 'Clientes con score ≥ este valor (y < score mín. Premium) son Estratégicos.',
            'score_min_default': 60,
            'descuento_default': 10,
            'titulo_default': 'Combo Estrategico',
            'descripcion_default': 'Descuento especial del 10% por tu volumen y fidelidad.',
        },
        {
            'clave_base': 'OFERTA_TIER_ESTANDAR',
            'nombre': 'Estándar',
            'color': 'green',
            'icono': 'verified',
            'tiene_score_min': True,
            'score_min_label': 'Score mínimo',
            'score_min_desc': 'Clientes con score ≥ este valor (y < score mín. Estratégico) son Estándar.',
            'score_min_default': 30,
            'descuento_default': 7,
            'titulo_default': 'Combo Estandar',
            'descripcion_default': 'Promocion del 7% en tu proximo pedido.',
        },
        {
            'clave_base': 'OFERTA_TIER_NUEVO',
            'nombre': 'Nuevo',
            'color': 'gray',
            'icono': 'person_add',
            'tiene_score_min': False,
            'score_min_label': None,
            'score_min_desc': None,
            'score_min_default': None,
            'descuento_default': 5,
            'titulo_default': 'Combo Bienvenida',
            'descripcion_default': 'Descuento de bienvenida del 5% en tu primer combo.',
        },
    ]

    if request.method == 'POST':
        grupo, _ = GrupoParametro.objects.get_or_create(
            codigo='OFERTAS_SEGMENTADAS',
            defaults={'nombre': 'Ofertas Segmentadas', 'descripcion': 'Parámetros de tiers de ofertas segmentadas (PI-1)'},
        )
        for tier in TIERS:
            base = tier['clave_base']
            if tier['tiene_score_min']:
                raw_min = request.POST.get(f'{base}_SCORE_MIN', '').strip()
                if raw_min:
                    try:
                        int(raw_min)
                        Parametro.set(f'{base}_SCORE_MIN', raw_min, tipo=Parametro.TIPO_INT,
                                      grupo=grupo, nombre=f"Score mín. {tier['nombre']}")
                    except ValueError:
                        pass

            raw_dsc = request.POST.get(f'{base}_DESCUENTO', '').strip()
            if raw_dsc:
                try:
                    int(raw_dsc)
                    Parametro.set(f'{base}_DESCUENTO', raw_dsc, tipo=Parametro.TIPO_INT,
                                  grupo=grupo, nombre=f"Descuento {tier['nombre']} (%)")
                except ValueError:
                    pass

            raw_tit = request.POST.get(f'{base}_TITULO', '').strip()
            if raw_tit:
                Parametro.set(f'{base}_TITULO', raw_tit, tipo=Parametro.TIPO_CADENA,
                              grupo=grupo, nombre=f"Título prefijo {tier['nombre']}")

            raw_desc = request.POST.get(f'{base}_DESCRIPCION', '').strip()
            if raw_desc:
                Parametro.set(f'{base}_DESCRIPCION', raw_desc, tipo=Parametro.TIPO_CADENA,
                              grupo=grupo, nombre=f"Descripción oferta {tier['nombre']}")

        return redirect(request.path + '?saved=1')

    # Construir lista de tiers con valores actuales
    tiers_con_valores = []
    for tier in TIERS:
        base = tier['clave_base']
        tiers_con_valores.append({
            **tier,
            'score_min_valor': Parametro.get(f'{base}_SCORE_MIN', tier['score_min_default']),
            'descuento_valor': Parametro.get(f'{base}_DESCUENTO', tier['descuento_default']),
            'titulo_valor': Parametro.get(f'{base}_TITULO', tier['titulo_default']),
            'descripcion_valor': Parametro.get(f'{base}_DESCRIPCION', tier['descripcion_default']),
        })

    saved = request.GET.get('saved') == '1'
    return render(request, 'configuracion/ofertas_segmentadas.html', {
        'tiers': tiers_con_valores,
        'saved': saved,
    })


def ofertas_hub(request):
    """Página índice de toda la configuración de Ofertas."""
    return render(request, 'configuracion/ofertas_hub.html')


@login_required
@requiere_permiso("Parametrizar el Sistema")
def ofertas_general_config(request):
    """Parámetros generales de la generación de ofertas: vigencia y periodicidad."""
    from configuracion.models import Parametro, GrupoParametro

    PARAMS = [
        {
            'clave': 'OFERTA_DIAS_VIGENCIA',
            'nombre': 'Días de vigencia de la oferta',
            'descripcion': (
                'Cantidad de días que tiene el cliente para responder una oferta antes de que se '
                'marque como vencida automáticamente. Valor por defecto: 30.'
            ),
            'tipo': Parametro.TIPO_INT,
            'input_type': 'number',
            'step': '1',
            'min': '1',
            'max': '365',
            'default': 30,
        },
        {
            'clave': 'RANKING_PERIODICIDAD',
            'nombre': 'Periodicidad del ranking',
            'descripcion': (
                'Define el período que se usa al generar el ranking de clientes y al agrupar ofertas. '
                '"mensual" agrupa por año-mes (2026-03); "trimestral" agrupa por año-trimestre (2026-Q1).'
            ),
            'tipo': Parametro.TIPO_CADENA,
            'input_type': 'select',
            'opciones': [('mensual', 'Mensual'), ('trimestral', 'Trimestral')],
            'default': 'mensual',
        },
    ]

    if request.method == 'POST':
        grupo, _ = GrupoParametro.objects.get_or_create(
            codigo='OFERTAS_GENERAL',
            defaults={'nombre': 'Ofertas — General', 'descripcion': 'Parámetros generales de generación de ofertas'},
        )
        for p in PARAMS:
            raw = request.POST.get(p['clave'], '').strip()
            if raw:
                Parametro.set(p['clave'], raw, tipo=p['tipo'], grupo=grupo, nombre=p['nombre'])
        return redirect(request.path + '?saved=1')

    saved = request.GET.get('saved') == '1'
    params_con_valor = [
        {**p, 'valor': Parametro.get(p['clave'], p['default'])}
        for p in PARAMS
    ]
    return render(request, 'configuracion/ofertas_general.html', {
        'params': params_con_valor,
        'saved': saved,
    })



@login_required
@requiere_permiso("Parametrizar el Sistema")
def automatizacion_compras_config(request):
    """Parametros de Automatizacion de Compras con criterios ponderados."""
    from configuracion.models import Parametro, GrupoParametro
    try:
        from core.motor.config import MotorConfig, DEFAULTS
    except Exception:
        MotorConfig = None
        DEFAULTS = {}

    PARAMS = [
        {
            'clave': 'AUTOPRESUPUESTO_VENTANA_DIAS',
            'nombre': 'Ventana de dias para pedidos recientes',
            'descripcion': 'Cantidad de dias hacia atras que se revisan pedidos para detectar faltantes de insumos.',
            'tipo': Parametro.TIPO_INT,
            'step': '1',
            'min': '1',
            'default': '7',
        },
        {
            'clave': 'STOCK_MINIMO_GLOBAL',
            'nombre': 'Stock minimo global',
            'descripcion': 'Nivel de stock por debajo del cual se genera automaticamente una Solicitud de Cotizacion al proveedor.',
            'tipo': Parametro.TIPO_INT,
            'step': '1',
            'min': '0',
            'default': '20',
        },
        {
            'clave': 'TOP_N_PROVEEDORES_COTIZACION',
            'nombre': 'Top N proveedores para SC automatica',
            'descripcion': 'Cantidad de proveedores rankeados que reciben la Solicitud de Cotizacion automaticamente.',
            'tipo': Parametro.TIPO_INT,
            'step': '1',
            'min': '1',
            'max': '10',
            'default': '5',
        },
        {
            'clave': 'AUTO_APROBAR_PROPUESTAS',
            'nombre': 'Auto-aprobar propuestas',
            'descripcion': 'Si esta activo, el sistema aprueba automaticamente las propuestas cuyo proveedor supera el umbral de score.',
            'tipo': Parametro.TIPO_BOOL,
            'default': 'False',
        },
        {
            'clave': 'UMBRAL_SCORE_PROVEEDOR',
            'nombre': 'Umbral de score para auto-aprobacion',
            'descripcion': 'Score minimo del proveedor (0-100) requerido para la auto-aprobacion de propuestas.',
            'tipo': Parametro.TIPO_FLOAT,
            'step': '0.5',
            'min': '0',
            'max': '100',
            'default': '70',
        },
    ]

    if request.method == 'POST':
        grupo, _ = GrupoParametro.objects.get_or_create(
            codigo='AUTOMATIZACION_COMPRAS',
            defaults={'nombre': 'Automatizacion Compras'},
        )
        for p in PARAMS:
            raw = request.POST.get(p['clave'], '').strip()
            if raw:
                Parametro.set(p['clave'], raw, tipo=p['tipo'], grupo=grupo, nombre=p['nombre'])
        return redirect(request.path + '?saved=1')

    saved = request.GET.get('saved') == '1'
    params_render = []
    for p in PARAMS:
        try:
            valor = Parametro.objects.get(clave=p['clave']).valor
        except Exception:
            valor = p.get('default', '')
        params_render.append({**p, 'valor': valor})

    return render(request, 'configuracion/parametros_genericos.html', {
        'titulo': 'Automatizacion de Compras',
        'subtitulo': 'Parametros que controlan el flujo automatico de cotizaciones y propuestas de compra.',
        'icono': 'shopping_cart_checkout',
        'color': 'emerald',
        'params': params_render,
        'saved': saved,
        'back_url': '/configuracion/',
    })
