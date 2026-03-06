from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from datetime import timedelta

from pedidos.models import Pedido
from productos.models import Producto
from clientes.models import Cliente


def _get_date_range(request):
    """Obtiene fechas 'desde' y 'hasta' desde query params en formato YYYY-MM-DD."""
    desde = parse_date(request.GET.get('desde') or '')
    hasta = parse_date(request.GET.get('hasta') or '')
    return desde, hasta


def dashboard_estadisticas(request):
    # Filtros opcionales
    desde, hasta = _get_date_range(request)

    # KPIs básicos
    total_clientes = Cliente.objects.count()
    total_productos = Producto.objects.count()
    total_pedidos = Pedido.objects.count()

    # Ingresos totales en rango (si lo hay), sino globales
    pedidos_qs = Pedido.objects.all()
    if desde:
        pedidos_qs = pedidos_qs.filter(fecha_pedido__gte=desde)
    if hasta:
        pedidos_qs = pedidos_qs.filter(fecha_pedido__lte=hasta)
    ingresos_totales = pedidos_qs.aggregate(total=Sum('monto_total'))['total'] or 0

    hoy = timezone.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_mes = hoy.replace(day=1)

    pedidos_hoy = pedidos_qs.filter(fecha_pedido=hoy).count()
    pedidos_semana = pedidos_qs.filter(fecha_pedido__gte=inicio_semana).count()
    pedidos_mes = pedidos_qs.filter(fecha_pedido__gte=inicio_mes).count()

    context = {
        'kpis': {
            'clientes': total_clientes,
            'productos': total_productos,
            'pedidos': total_pedidos,
            'ingresos_totales': float(ingresos_totales),
            'pedidos_hoy': pedidos_hoy,
            'pedidos_semana': pedidos_semana,
            'pedidos_mes': pedidos_mes,
        },
        'filtros': {
            'desde': desde.isoformat() if desde else '',
            'hasta': hasta.isoformat() if hasta else '',
        }
    }
    return render(request, 'estadisticas/dashboard.html', context)


def api_kpis(request):
    desde, hasta = _get_date_range(request)
    total_clientes = Cliente.objects.count()
    total_productos = Producto.objects.count()
    total_pedidos = Pedido.objects.count()
    pedidos_qs = Pedido.objects.all()
    if desde:
        pedidos_qs = pedidos_qs.filter(fecha_pedido__gte=desde)
    if hasta:
        pedidos_qs = pedidos_qs.filter(fecha_pedido__lte=hasta)
    ingresos_totales = pedidos_qs.aggregate(total=Sum('monto_total'))['total'] or 0
    hoy = timezone.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_mes = hoy.replace(day=1)
    pedidos_hoy = pedidos_qs.filter(fecha_pedido=hoy).count()
    pedidos_semana = pedidos_qs.filter(fecha_pedido__gte=inicio_semana).count()
    pedidos_mes = pedidos_qs.filter(fecha_pedido__gte=inicio_mes).count()
    return JsonResponse({
        'clientes': total_clientes,
        'productos': total_productos,
        'pedidos': total_pedidos,
        'ingresos_totales': float(ingresos_totales),
        'pedidos_hoy': pedidos_hoy,
        'pedidos_semana': pedidos_semana,
        'pedidos_mes': pedidos_mes,
    })


def api_pedidos_por_estado(request):
    desde, hasta = _get_date_range(request)
    qs = Pedido.objects.all()
    if desde:
        qs = qs.filter(fecha_pedido__gte=desde)
    if hasta:
        qs = qs.filter(fecha_pedido__lte=hasta)
    data = (
        qs.values('estado__nombre')
        .annotate(cantidad=Count('id'))
        .order_by('estado__nombre')
    )
    labels = [(d['estado__nombre'] or 'Sin estado') for d in data]
    values = [d['cantidad'] for d in data]
    return JsonResponse({'labels': labels, 'values': values})


def api_ingresos_por_mes(request):
    hoy = timezone.now().date()
    desde, hasta = _get_date_range(request)
    qs = Pedido.objects.all()
    if not desde and not hasta:
        # Default: últimos 6 meses
        desde = hoy - timedelta(days=31 * 6)
    if desde:
        qs = qs.filter(fecha_pedido__gte=desde)
    if hasta:
        qs = qs.filter(fecha_pedido__lte=hasta)
    data = (
        qs.annotate(mes=TruncMonth('fecha_pedido'))
        .values('mes')
        .annotate(total=Sum('monto_total'))
        .order_by('mes')
    )
    labels = [d['mes'].strftime('%Y-%m') if d['mes'] else 'N/A' for d in data]
    values = [float(d['total'] or 0) for d in data]
    return JsonResponse({'labels': labels, 'values': values})


def api_top_productos(request):
    desde, hasta = _get_date_range(request)
    qs = Pedido.objects.all()
    if desde:
        qs = qs.filter(fecha_pedido__gte=desde)
    if hasta:
        qs = qs.filter(fecha_pedido__lte=hasta)
    data = (
        qs.values('producto__nombreProducto')
        .annotate(total=Sum('monto_total'))
        .order_by('-total')[:5]
    )
    labels = [d['producto__nombreProducto'] or 'Desconocido' for d in data]
    values = [float(d['total'] or 0) for d in data]
    return JsonResponse({'labels': labels, 'values': values})


# ── APIs de inteligencia (proyecciones desde los motores) ────────────────────

def api_top_clientes_score(request):
    """
    Devuelve los N clientes con mayor score estratégico.
    Query param: n (default 10).
    """
    try:
        from automatizacion.models import RankingCliente
    except ImportError:
        return JsonResponse({'error': 'módulo automatizacion no disponible'}, status=500)

    n = int(request.GET.get('n', 10))
    qs = (
        RankingCliente.objects
        .select_related('cliente')
        .order_by('-score')[:n]
    )

    TIERS = [
        ('Premium',     90),
        ('Estratégico', 60),
        ('Estándar',    30),
        ('Nuevo',        0),
    ]

    def _tier(score):
        for nombre, minimo in TIERS:
            if score >= minimo:
                return nombre
        return 'Nuevo'

    clientes = []
    for rc in qs:
        clientes.append({
            'id':     rc.cliente_id,
            'nombre': str(rc.cliente),
            'score':  round(float(rc.score), 1),
            'tier':   _tier(float(rc.score)),
        })

    return JsonResponse({'clientes': clientes})


def api_insumos_urgentes(request):
    """
    Ejecuta el motor de demanda y devuelve únicamente las acciones de prioridad alta.
    Respuesta rápida: usa datos ya calculados en el último ciclo si están disponibles.
    """
    try:
        from core.motor.demanda_engine import DemandaInteligenteEngine
        engine = DemandaInteligenteEngine()
        resultado = engine.ejecutar()
        urgentes = [a for a in resultado.get('detalle', []) if a.get('prioridad') == 'alta']
    except Exception as e:
        return JsonResponse({'error': str(e), 'urgentes': []}, status=500)

    return JsonResponse({
        'urgentes': urgentes,
        'total_insumos_procesados': resultado.get('insumos_procesados', 0),
        'total_acciones': resultado.get('acciones_sugeridas', 0),
        'periodo': resultado.get('periodo', ''),
    })


def api_proyeccion_demanda(request):
    """
    Proyecta la demanda de los N insumos más relevantes.

    Jerarquía de fuentes por insumo:
        1. ProyeccionInsumo del período actual (dato oficial del motor de demanda).
        2. Media móvil de ConsumoRealInsumo de los últimos MESES meses.
        3. Media mensual de OrdenCompra de los últimos 6 meses (proxy real).
        4. insumo.cantidad (cantidad típica de compra definida en el catálogo).
        5. stock_minimo_manual como proxy de consumo mensual PYME.

    Query params: n (default 8), meses (default 3).
    """
    try:
        from insumos.models import Insumo, ProyeccionInsumo, predecir_demanda_media_movil
        from pedidos.models import OrdenCompra
        from django.utils import timezone
        from django.db.models import Sum
        from datetime import timedelta
        from core.motor.config import MotorConfig

        _n_default = MotorConfig.get('PROYECCION_N_INSUMOS', cast=int)
        _m_default = MotorConfig.get('PROYECCION_MESES', cast=int)
        n = int(request.GET.get('n', _n_default if _n_default is not None else 8))
        meses = int(request.GET.get('meses', _m_default if _m_default is not None else 3))
    except Exception as e:
        return JsonResponse({'error': str(e), 'proyecciones': []}, status=500)

    try:
        hoy = timezone.now()
        periodo_actual = hoy.strftime('%Y-%m')

        # Pre-cargar proyecciones del período actual para evitar N queries
        proyecciones_bd = {
            p.insumo_id: p.cantidad_proyectada
            for p in ProyeccionInsumo.objects.filter(periodo=periodo_actual)
        }

        # Pre-cargar media mensual de ordenes de compra (últimos 6 meses) por insumo
        hace_6m = hoy - timedelta(days=180)
        ordenes_por_insumo = {}
        for row in (
            OrdenCompra.objects
            .filter(fecha_creacion__gte=hace_6m)
            .values('insumo_id')
            .annotate(total=Sum('cantidad'))
        ):
            ordenes_por_insumo[row['insumo_id']] = row['total'] / 6.0  # promedio mensual

        # Solo insumos directos (se incorporan al producto final)
        # Insumos con proyección explícita primero, luego por stock (más críticos)
        insumos_con_proy = list(
            Insumo.objects.filter(activo=True, tipo=Insumo.TIPO_DIRECTO, idInsumo__in=proyecciones_bd.keys())
        )
        insumos_sin_proy = list(
            Insumo.objects.filter(activo=True, tipo=Insumo.TIPO_DIRECTO)
            .exclude(idInsumo__in=proyecciones_bd.keys())
            .order_by('stock')[:n * 2]
        )
        insumos = (insumos_con_proy + insumos_sin_proy)[:n * 3]

        proyecciones = []
        for insumo in insumos:
            # 1) ProyeccionInsumo oficial
            demanda = proyecciones_bd.get(insumo.idInsumo)

            # 2) Media móvil de ConsumoRealInsumo
            if demanda is None:
                demanda = predecir_demanda_media_movil(insumo, periodo_actual, meses=meses)

            # 3) Media de OrdenCompra
            if demanda is None or demanda == 0:
                demanda = ordenes_por_insumo.get(insumo.idInsumo)

            # 4) cantidad típica del catálogo
            if demanda is None or demanda == 0:
                demanda = float(insumo.cantidad or 0)

            # 5) stock mínimo manual como proxy de consumo mensual PYME
            if demanda is None or demanda == 0:
                demanda = float(insumo.stock_minimo_manual or 0)

            demanda = float(demanda or 0)
            proyecciones.append({
                'insumo_id':          insumo.idInsumo,
                'nombre':             insumo.nombre,
                'codigo':             insumo.codigo,
                'stock_actual':       float(insumo.stock or 0),
                'stock_minimo':       float(insumo.stock_minimo_sugerido or 0),
                'demanda_proyectada': round(demanda, 1),
                'diferencia':         round(float(insumo.stock or 0) - demanda, 1),
                'fuente':             (
                    'proyeccion' if insumo.idInsumo in proyecciones_bd else
                    'ordenes'    if insumo.idInsumo in ordenes_por_insumo else
                    'catalogo'
                ),
            })

        # Más críticos primero (menor diferencia stock - demanda)
        proyecciones.sort(key=lambda x: x['diferencia'])
        proyecciones = proyecciones[:n]

        return JsonResponse({'proyecciones': proyecciones, 'periodo': periodo_actual, 'ventana_meses': meses})

    except Exception as e:
        return JsonResponse({'error': str(e), 'proyecciones': []}, status=500)


def api_resumen_inteligencia(request):
    """
    Resumen ejecutivo del estado de los 3 motores inteligentes.
    No ejecuta los motores completos; lee datos ya persistidos para velocidad.
    """
    try:
        from automatizacion.models import (
            RankingCliente, ScoreProveedor, CompraPropuesta, OfertaPropuesta
        )
        from insumos.models import Insumo
        from django.conf import settings
        import os

        # Motor 1 — clientes
        total_clientes_rankeados = RankingCliente.objects.count()
        score_promedio = RankingCliente.objects.aggregate(avg=Sum('score'))['avg'] or 0
        if total_clientes_rankeados:
            score_promedio = score_promedio / total_clientes_rankeados
        ofertas_pendientes = OfertaPropuesta.objects.filter(estado='pendiente').count()
        ofertas_enviadas   = OfertaPropuesta.objects.filter(estado='enviada').count()

        # Motor 2 — proveedores
        total_prov_rankeados = ScoreProveedor.objects.count()
        mejor_proveedor = (
            ScoreProveedor.objects
            .select_related('proveedor')
            .order_by('-score')
            .first()
        )

        # Motor 3 — insumos
        insumos_sin_stock = Insumo.objects.filter(activo=True, stock=0).count()
        # stock_minimo_sugerido es una @property Python, no una columna DB → evaluar en Python
        insumos_bajo_min = sum(
            1 for ins in Insumo.objects.filter(activo=True, stock__gt=0)
            if ins.stock < ins.stock_minimo_sugerido
        )
        propuestas_compra_pendientes = CompraPropuesta.objects.filter(estado='pendiente').count()

        # Modelos ML activos (verificar existencia de los 3 pkl)
        def _ml_activo(nombre_pkl):
            path = os.path.normpath(
                os.path.join(settings.BASE_DIR, '..', 'core', 'ai_ml', nombre_pkl)
            )
            return os.path.exists(path)

        ml_clientes    = _ml_activo('modelo_valor_cliente.pkl')
        ml_proveedores = _ml_activo('modelo_score_proveedor.pkl')
        ml_insumos     = _ml_activo('modelo_demanda_insumo.pkl')

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({
        'motor_clientes': {
            'clientes_rankeados':  total_clientes_rankeados,
            'score_promedio':      round(score_promedio, 1),
            'ofertas_pendientes':  ofertas_pendientes,
            'ofertas_enviadas':    ofertas_enviadas,
            'ml_activo':           ml_clientes,
        },
        'motor_proveedores': {
            'proveedores_rankeados': total_prov_rankeados,
            'mejor_proveedor': str(mejor_proveedor.proveedor) if mejor_proveedor else None,
            'mejor_score':     round(float(mejor_proveedor.score), 1) if mejor_proveedor else None,
            'ml_activo':       ml_proveedores,
        },
        'motor_insumos': {
            'sin_stock':                insumos_sin_stock,
            'bajo_minimo':              insumos_bajo_min,
            'propuestas_compra_pendientes': propuestas_compra_pendientes,
            'ml_activo':                ml_insumos,
        },
    })
