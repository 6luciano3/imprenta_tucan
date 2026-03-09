from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from datetime import timedelta

from pedidos.models import Pedido, LineaPedido
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
    qs = LineaPedido.objects.all()
    if desde:
        qs = qs.filter(pedido__fecha_pedido__gte=desde)
    if hasta:
        qs = qs.filter(pedido__fecha_pedido__lte=hasta)
    data = (
        qs.values('producto__nombreProducto')
        .annotate(total=Sum('precio_unitario'))
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
    Ejecuta el motor de demanda y devuelve acciones de prioridad alta y crítica.
    Usa caché de 2 minutos para evitar recalcular en cada carga del dashboard.
    Param ?refresh=1  → invalida la caché y recalcula de inmediato.
    """
    from django.core.cache import cache
    _CACHE_KEY = 'insumos_urgentes_resultado'
    _CACHE_TTL = 2 * 60  # 2 minutos

    try:
        from core.motor.demanda_engine import DemandaInteligenteEngine
        if request.GET.get('refresh'):
            cache.delete(_CACHE_KEY)
        resultado = cache.get(_CACHE_KEY)
        if resultado is None:
            engine = DemandaInteligenteEngine()
            resultado = engine.ejecutar()
            cache.set(_CACHE_KEY, resultado, _CACHE_TTL)
        # Incluir prioridad 'critica' (R1: sin stock) además de 'alta' (R2/R4)
        urgentes = [
            a for a in resultado.get('detalle', [])
            if a.get('prioridad') in ('alta', 'critica')
        ]
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
        2. Media móvil ponderada de ConsumoRealInsumo de los últimos MESES meses.
        3. Media mensual de OrdenCompra de los últimos 6 meses (divide por meses reales
           con actividad, no siempre por 6).
        4. insumo.cantidad (cantidad típica de compra definida en el catálogo).
        5. stock_minimo_manual como proxy de consumo mensual PYME.

    Aplica factor estacional (mismo mes vs. promedio histórico ponderado por año)
    a las fuentes 2–5 para ajustar la proyección al período actual.

    Query params: n (default 8), meses (default 3).
    """
    try:
        from insumos.models import Insumo, ProyeccionInsumo, predecir_demanda_media_movil
        from pedidos.models import OrdenCompra
        from django.utils import timezone
        from django.db.models import Sum
        from django.db.models.functions import TruncMonth
        from datetime import timedelta
        from core.motor.config import MotorConfig
        from core.motor.demanda_engine import DemandaInteligenteEngine

        _n_default = MotorConfig.get('PROYECCION_N_INSUMOS', cast=int)
        _m_default = MotorConfig.get('PROYECCION_MESES', cast=int)
        n = int(request.GET.get('n', _n_default if _n_default is not None else 8))
        meses = int(request.GET.get('meses', _m_default if _m_default is not None else 3))
    except Exception as e:
        return JsonResponse({'error': str(e), 'proyecciones': []}, status=500)

    try:
        hoy = timezone.now()
        periodo_actual = hoy.strftime('%Y-%m')
        mes_actual = hoy.month
        engine = DemandaInteligenteEngine()

        # Pre-cargar proyecciones del período actual para evitar N queries
        proyecciones_bd = {
            p.insumo_id: p.cantidad_proyectada
            for p in ProyeccionInsumo.objects.filter(periodo=periodo_actual)
        }

        # Pre-cargar media mensual de órdenes de compra (últimos 6 meses) por insumo.
        # Divide por los meses reales con actividad, no siempre por 6.
        hace_6m = hoy - timedelta(days=180)
        ordenes_por_insumo = {}
        meses_activos_por_insumo = {}
        for row in (
            OrdenCompra.objects
            .filter(fecha_creacion__gte=hace_6m)
            .values('insumo_id')
            .annotate(total=Sum('cantidad'))
        ):
            ordenes_por_insumo[row['insumo_id']] = row['total']
        for row in (
            OrdenCompra.objects
            .filter(fecha_creacion__gte=hace_6m)
            .annotate(mes=TruncMonth('fecha_creacion'))
            .values('insumo_id', 'mes')
            .distinct()
        ):
            meses_activos_por_insumo[row['insumo_id']] = (
                meses_activos_por_insumo.get(row['insumo_id'], 0) + 1
            )
        # Calcular promedio mensual real para cada insumo
        ordenes_promedio_por_insumo = {
            iid: total / meses_activos_por_insumo.get(iid, 1)
            for iid, total in ordenes_por_insumo.items()
        }

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
            fuente = 'catalogo'

            # 1) ProyeccionInsumo oficial — ya incluye ajuste estacional del motor
            demanda = proyecciones_bd.get(insumo.idInsumo)
            if demanda is not None:
                fuente = 'proyeccion'

            # 2) Media móvil ponderada de ConsumoRealInsumo + factor estacional
            if demanda is None:
                demanda = predecir_demanda_media_movil(insumo, periodo_actual, meses=meses)
                if demanda is not None and demanda > 0:
                    fuente = 'media_movil'

            # 3) Media de OrdenCompra por meses reales + factor estacional
            if demanda is None or demanda == 0:
                prom = ordenes_promedio_por_insumo.get(insumo.idInsumo)
                if prom:
                    demanda = prom
                    fuente = 'ordenes'

            # 4) Cantidad típica del catálogo
            if demanda is None or demanda == 0:
                demanda = float(insumo.cantidad or 0)
                if demanda > 0:
                    fuente = 'catalogo'

            # 5) Stock mínimo manual como proxy de consumo mensual PYME
            if demanda is None or demanda == 0:
                demanda = float(insumo.stock_minimo_manual or 0)
                if demanda > 0:
                    fuente = 'stock_minimo'

            demanda = float(demanda or 0)

            # Aplicar factor estacional a fuentes que no son la proyección oficial
            # (la proyección oficial ya lo incorpora en el motor de demanda)
            if fuente != 'proyeccion' and demanda > 0:
                factor = engine._factor_estacional(insumo, mes_actual)
                demanda = max(0.0, demanda * factor)

            # Cap de sanity: fuentes sin historial real (ordenes/catalogo/stock_minimo)
            # no deben superar un máximo razonable. Se usa el mayor entre:
            #   - stock_minimo_sugerido * 10  (estimación conservadora mensual)
            #   - stock_actual * 5            (5 veces el stock disponible)
            # Esto evita que datos de prueba o packs inflados dominen la proyección.
            if fuente in ('ordenes', 'catalogo', 'stock_minimo'):
                stock_min = float(insumo.stock_minimo_sugerido or 0)
                stock_act = float(insumo.stock or 0)
                cap = max(stock_min * 10, stock_act * 5, 50.0)
                demanda = min(demanda, cap)

            proyecciones.append({
                'insumo_id':          insumo.idInsumo,
                'nombre':             insumo.nombre,
                'codigo':             insumo.codigo,
                'stock_actual':       float(insumo.stock or 0),
                'stock_minimo':       float(insumo.stock_minimo_sugerido or 0),
                'demanda_proyectada': round(demanda, 1),
                'diferencia':         round(float(insumo.stock or 0) - demanda, 1),
                'fuente':             fuente,
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
