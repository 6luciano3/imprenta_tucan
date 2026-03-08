# Thin wrappers para invocación directa (sin Celery).
# Las implementaciones completas están en automatizacion/tasks.py como @shared_task.
from datetime import timedelta
from django.utils import timezone


def tarea_prediccion_demanda():
    from core.motor import MotorProcesosInteligentes
    return MotorProcesosInteligentes.ejecutar('demanda')


def tarea_anticipacion_compras():
    from core.ai_rules.rules_engine import evaluar_reglas
    from insumos.models import Insumo, predecir_demanda_media_movil
    periodo = timezone.now().strftime('%Y-%m')
    insumos_data = [
        {
            'id': i.idInsumo,
            'nombre': i.nombre,
            'stock': int(i.stock or 0),
            'stock_minimo': int(i.stock_minimo_sugerido or 0),
            'demanda_predicha': int(predecir_demanda_media_movil(i, periodo, meses=3) or 0),
        }
        for i in Insumo.objects.filter(activo=True)
    ]
    return evaluar_reglas({'insumos': insumos_data})


def tarea_ranking_clientes():
    from core.ai_ml.ranking import calcular_ranking_clientes
    return calcular_ranking_clientes()


def tarea_generar_ofertas():
    from core.ai_ml.ofertas import generar_ofertas_segmentadas
    return generar_ofertas_segmentadas()


def tarea_alertas_retraso():
    from core.automation.alertas import revisar_pedidos_retrasados
    return revisar_pedidos_retrasados()
