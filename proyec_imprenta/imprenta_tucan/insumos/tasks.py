from celery import shared_task
from insumos.models import ProyeccionInsumo, Insumo
from pedidos.models import Pedido
from proveedores.models import Proveedor
from django.utils import timezone

@shared_task
def generar_proyecciones_insumos():
    """
    Genera proyecciones mensuales de demanda para cada insumo activo.

    Algoritmo usado: determinado por el parámetro ALGORITMO_PROYECCION
        - 'media_movil' (default): media móvil ponderada de los últimos N meses.
        - 'ets': suavizado exponencial (ETS) sobre los últimos M meses.

    Fallbacks (en orden):
        1. stock_minimo_sugerido del insumo si el algoritmo no devuelve datos.
        2. Si tampoco hay mínimo sugerido (0), el insumo se omite.

    El campo `fuente` registra de dónde proviene el valor proyectado.
    """
    from insumos.models import predecir_demanda_media_movil, predecir_demanda_ets
    from core.motor.config import MotorConfig

    periodo = timezone.now().strftime('%Y-%m')
    meses = MotorConfig.get('PROYECCION_MESES', cast=int) or 3
    algoritmo = str(MotorConfig.get('ALGORITMO_PROYECCION') or 'media_movil').strip()
    generadas = 0
    omitidas = 0

    for insumo in Insumo.objects.filter(activo=True):
        fuente = algoritmo

        if algoritmo == 'ets':
            cantidad_proyectada = predecir_demanda_ets(insumo, periodo)
        else:
            cantidad_proyectada = predecir_demanda_media_movil(insumo, periodo, meses=meses)

        if cantidad_proyectada is None:
            # Fallback: usar stock mínimo sugerido
            fallback = int(insumo.stock_minimo_sugerido or 0)
            if fallback > 0:
                cantidad_proyectada = fallback
                fuente = ProyeccionInsumo.FUENTE_STOCK_MINIMO
            else:
                omitidas += 1
                continue

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
                'fuente': fuente,
            },
        )
        generadas += 1

    return f'Proyecciones generadas: {generadas} | Sin datos (omitidas): {omitidas}'
