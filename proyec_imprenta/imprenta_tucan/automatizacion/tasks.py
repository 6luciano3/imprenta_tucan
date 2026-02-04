from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count

from automatizacion.models import RankingCliente, ScoreProveedor
from clientes.models import Cliente
from pedidos.models import Pedido
from proveedores.models import Proveedor

# Integraciones AI/Rules (placeholders con llamadas reales si se completan módulos)
try:
    from core.ai_ml.demand_prediction import predecir_demanda
except Exception:
    predecir_demanda = None

try:
    from core.ai_rules.rules_engine import evaluar_reglas
except Exception:
    evaluar_reglas = None


@shared_task
def tarea_prediccion_demanda():
    # Ejecutar predicción de demanda para insumos críticos si está disponible
    if predecir_demanda is None:
        return "prediccion_demanda: módulo no disponible"
    # Ejemplo mínimo (debería iterar insumos y su histórico real)
    try:
        # Placeholder: no hay modelo de Insumo en este módulo
        return "prediccion_demanda: ejecutado (placeholder)"
    except Exception as e:
        return f"prediccion_demanda: error {e}"


@shared_task
def tarea_anticipacion_compras():
    # Aplicar reglas de anticipación si hay motor de reglas
    if evaluar_reglas is None:
        return "anticipacion_compras: rules engine no disponible"
    try:
        contexto = {"fecha": timezone.now()}
        decisiones = evaluar_reglas(contexto)
        return f"anticipacion_compras: {len(decisiones)} decisiones"
    except Exception as e:
        return f"anticipacion_compras: error {e}"


@shared_task
def tarea_ranking_clientes():
    # Recalcular RankingCliente basado en actividad de pedidos últimos 90 días
    try:
        desde = timezone.now().date() - timedelta(days=90)
        agregados = (
            Pedido.objects.filter(fecha_pedido__gte=desde)
            .values('cliente_id')
            .annotate(total=Sum('monto_total'), cantidad=Count('id'))
        )
        if not agregados:
            return "ranking_clientes: sin datos recientes"
        max_total = max(a['total'] or 0 for a in agregados) or 1
        max_cant = max(a['cantidad'] or 0 for a in agregados) or 1
        for a in agregados:
            total_norm = (a['total'] or 0) / max_total
            cant_norm = (a['cantidad'] or 0) / max_cant
            score = round(0.7 * total_norm + 0.3 * cant_norm, 4) * 100
            RankingCliente.objects.update_or_create(
                cliente_id=a['cliente_id'],
                defaults={'score': score}
            )
        return f"ranking_clientes: {len(agregados)} clientes actualizados"
    except Exception as e:
        return f"ranking_clientes: error {e}"


@shared_task
def tarea_recalcular_scores_proveedores():
    # Recalcular ScoreProveedor para todos los proveedores activos
    try:
        from automatizacion.api.services import ProveedorInteligenteService
        count = 0
        for proveedor in Proveedor.objects.filter(activo=True):
            score = ProveedorInteligenteService.calcular_score(proveedor, insumo=None)
            ScoreProveedor.objects.update_or_create(
                proveedor=proveedor,
                defaults={'score': score}
            )
            count += 1
        return f"scores_proveedores: {count} proveedores actualizados"
    except Exception as e:
        return f"scores_proveedores: error {e}"


@shared_task
def tarea_generar_ofertas():
    # Generar ofertas automáticas basadas en reglas (placeholder)
    try:
        # Conectar a core.ai_ml.ofertas si existe
        return "generar_ofertas: ejecutado (placeholder)"
    except Exception as e:
        return f"generar_ofertas: error {e}"


@shared_task
def tarea_alertas_retraso():
    # Emitir alertas según reglas/umbrales (placeholder)
    try:
        return "alertas_retraso: ejecutado (placeholder)"
    except Exception as e:
        return f"alertas_retraso: error {e}"
