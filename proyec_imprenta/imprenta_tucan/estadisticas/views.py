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
