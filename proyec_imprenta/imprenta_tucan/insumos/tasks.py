from celery import shared_task
from insumos.models import ProyeccionInsumo, Insumo
from pedidos.models import Pedido
from proveedores.models import Proveedor
from django.utils import timezone

@shared_task
def generar_proyecciones_insumos():
    # Ejemplo simple: sumar pedidos del último año y proyectar para el próximo mes
    periodo = timezone.now().strftime('%Y-%m')
    for insumo in Insumo.objects.all():
        pedidos = Pedido.objects.filter(insumo=insumo, fecha__year=timezone.now().year-1)
        cantidad_total = sum(p.cantidad for p in pedidos)
        cantidad_proyectada = int(cantidad_total / 12 * 1.1)  # Promedio mensual + 10%
        proveedor = insumo.proveedor
        ProyeccionInsumo.objects.update_or_create(
            insumo=insumo,
            periodo=periodo,
            defaults={
                'cantidad_proyectada': cantidad_proyectada,
                'proveedor_sugerido': proveedor,
                'estado': 'pendiente',
            }
        )
    return 'Proyecciones generadas.'
