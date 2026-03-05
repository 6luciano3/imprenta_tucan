from celery import shared_task
from insumos.models import ProyeccionInsumo, Insumo
from pedidos.models import Pedido
from proveedores.models import Proveedor
from django.utils import timezone

@shared_task
def generar_proyecciones_insumos():
    """
    Genera proyecciones mensuales de demanda usando media móvil sobre ConsumoRealInsumo.

    Algoritmo:
        - Media simple de los últimos 3 meses de consumo real registrado.
        - Fallback: stock_minimo_sugerido del insumo (calculado desde consumo promedio).
        - Si tampoco hay mínimo sugerido, omite el insumo.
    """
    from insumos.models import predecir_demanda_media_movil

    periodo = timezone.now().strftime('%Y-%m')
    generadas = 0
    omitidas = 0

    for insumo in Insumo.objects.filter(activo=True):
        cantidad_proyectada = predecir_demanda_media_movil(insumo, periodo, meses=3)

        if cantidad_proyectada is None:
            # Fallback: usar stock mínimo sugerido
            cantidad_proyectada = int(insumo.stock_minimo_sugerido or 0)

        if cantidad_proyectada == 0:
            omitidas += 1
            continue

        ProyeccionInsumo.objects.update_or_create(
            insumo=insumo,
            periodo=periodo,
            defaults={
                'cantidad_proyectada': cantidad_proyectada,
                'proveedor_sugerido': insumo.proveedor,
                'estado': 'pendiente',
            },
        )
        generadas += 1

    return f'Proyecciones generadas: {generadas} | Sin datos (omitidas): {omitidas}'
