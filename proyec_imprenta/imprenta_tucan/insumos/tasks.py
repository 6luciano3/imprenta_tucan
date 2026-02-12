from celery import shared_task
from insumos.models import ProyeccionInsumo, Insumo
from pedidos.models import Pedido
from proveedores.models import Proveedor
from django.utils import timezone

@shared_task
def generar_proyecciones_insumos():
    # DEMO: Generar proyecciones diarias con cantidades inventadas aleatorias
    import random
    periodo = timezone.now().strftime('%Y-%m-%d')  # Proyección diaria
    for insumo in Insumo.objects.all():
        cantidad_proyectada = random.randint(50, 500)  # Valor inventado para demo
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
    return 'Proyecciones diarias generadas (DEMO).'
