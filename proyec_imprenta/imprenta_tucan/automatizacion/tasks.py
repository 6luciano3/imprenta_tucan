import logging
from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from automatizacion.models import ScoreProveedor, OfertaPropuesta
import requests
from configuracion.models import Parametro
from pedidos.models import Pedido
from proveedores.models import Proveedor

logger = logging.getLogger(__name__)

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
    """
    Ejecuta PI-3 (DemandaInteligenteEngine): predice demanda con media móvil
    y aplica reglas de stock para todos los insumos activos.
    """
    try:
        from core.motor import MotorProcesosInteligentes
        resultado = MotorProcesosInteligentes.ejecutar('demanda')
        procesados = resultado.get('insumos_procesados', 0)
        acciones = resultado.get('acciones_sugeridas', 0)
        urgentes = resultado.get('urgentes', 0)
        return f"prediccion_demanda: {procesados} insumos, {acciones} acciones sugeridas ({urgentes} urgentes)"
    except Exception as e:
        return f"prediccion_demanda: error {e}"


@shared_task
def tarea_anticipacion_compras():
    """
    Aplica el motor de reglas sobre el estado actual del stock e insumos
    con demanda predicha para anticipar compras necesarias.
    """
    try:
        from insumos.models import Insumo, predecir_demanda_media_movil
        from core.ai_rules.rules_engine import evaluar_reglas

        periodo = timezone.now().strftime('%Y-%m')
        insumos_data = []
        for insumo in Insumo.objects.filter(activo=True, tipo=Insumo.TIPO_DIRECTO):
            demanda = predecir_demanda_media_movil(insumo, periodo, meses=3) or 0
            insumos_data.append({
                'id': insumo.idInsumo,
                'nombre': insumo.nombre,
                'stock': int(insumo.stock or 0),
                'stock_minimo': int(insumo.stock_minimo_sugerido or 0),
                'demanda_predicha': int(demanda),
            })

        from pedidos.models import Pedido as PedidoModel
        pedidos_retrasados = PedidoModel.objects.filter(
            estado__nombre__icontains='retras'
        ).count()

        contexto = {
            'insumos': insumos_data,
            'pedidos_retrasados': pedidos_retrasados,
            'fecha': timezone.now(),
        }
        decisiones = evaluar_reglas(contexto)
        criticas = sum(1 for d in decisiones if d.get('prioridad') == 'critica')

        # Anticipación proactiva: detectar insumos que agotarán stock
        # antes del lead time aunque aún no estén bajo el mínimo
        try:
            from core.ai_ml.anticipation import anticipar_compras
            anticipaciones = 0
            for item in insumos_data:
                resultado_ant = anticipar_compras(item['id'], item['demanda_predicha'])
                if resultado_ant and resultado_ant.get('urgencia') in ('critica', 'alta'):
                    anticipaciones += 1
                    decisiones.append({
                        'tipo': 'anticipacion_proactiva',
                        'insumo_id': item['id'],
                        'insumo_nombre': item['nombre'],
                        'cantidad_sugerida': resultado_ant['cantidad_sugerida'],
                        'prioridad': resultado_ant['urgencia'],
                        'accion': resultado_ant['motivo'],
                    })
        except Exception:
            anticipaciones = 0

        return (
            f"anticipacion_compras: {len(decisiones)} decisiones ({criticas} críticas, "
            f"{anticipaciones} anticipaciones proactivas)"
        )
    except Exception as e:
        return f"anticipacion_compras: error {e}"


@shared_task
def tarea_ranking_clientes():
    """Thin wrapper: delega toda la lógica a core/ai_ml/ranking.py."""
    try:
        from core.ai_ml.ranking import calcular_ranking_clientes
        resultado = calcular_ranking_clientes()
        msg = f"ranking_clientes: {resultado['actualizados']} clientes actualizados ({resultado['periodo']})"
    except Exception as e:
        return f"ranking_clientes: error {e}"

    # Tras recalcular el ranking, detectar ascensos de tier y activar campañas
    try:
        from core.automation.campanas import detectar_y_activar_campanas_tier
        res_camp = detectar_y_activar_campanas_tier()
        msg += f" | campañas activadas: {res_camp.get('campanas_activadas', 0)}"
    except Exception as e:
        msg += f" | campañas: error {e}"

    return msg


@shared_task
def tarea_recalcular_scores_proveedores():
    """
    Recalcula ScoreProveedor usando PI-2 (ProveedorInteligenteEngine).
    Pesos leidos desde ProveedorParametro (BD); métricas reales de precio
    relativo y disponibilidad histórica.
    """
    try:
        from core.motor.proveedor_engine import ProveedorInteligenteEngine
        # recomendar() usa _calcular_scores_batch(): 4-5 queries totales en lugar de N*5
        engine = ProveedorInteligenteEngine()
        engine.recomendar(insumo=None)
        count = Proveedor.objects.filter(activo=True).count()
        return f"scores_proveedores: {count} proveedores actualizados"
    except Exception as e:
        return f"scores_proveedores: error {e}"


@shared_task
def tarea_generar_ofertas():
    """Thin wrapper: delega toda la lógica a core/ai_ml/ofertas.py."""
    try:
        from core.ai_ml.ofertas import generar_ofertas_segmentadas
        resultado = generar_ofertas_segmentadas()
        return f"generar_ofertas: {resultado['generadas']} propuestas generadas ({resultado['periodo']})"
    except Exception as e:
        return f"generar_ofertas: error {e}"

@shared_task
def tarea_alertas_retraso():
    """Revisa todos los pedidos activos y emite alertas de retraso."""
    try:
        from core.automation.alertas import revisar_pedidos_retrasados
        resultado = revisar_pedidos_retrasados()
        return (
            f"alertas_retraso: {resultado['revisados']} revisados, "
            f"{resultado['retrasados']} retrasados, {resultado['alertas_enviadas']} alertas enviadas"
        )
    except Exception as e:
        return f"alertas_retraso: error {e}"


# CANTIDADES_COMPRA fue eliminado — use insumo.cantidad_compra_sugerida (ver migration 0009)
# Para poblar el campo ejecute: python manage.py poblar_cantidad_compra


# ---------------------------------------------------------------------------
# Helpers privados para tarea_automatizacion_presupuestos_ponderada
# ---------------------------------------------------------------------------

def _consultar_stock_http(proveedor, insumo, cantidad_req, consulta):
    """Envía consulta HTTP al proveedor (fuera de atomic) y actualiza ConsultaStockProveedor."""
    if not proveedor.api_stock_url:
        return
    try:
        resp = requests.post(
            proveedor.api_stock_url,
            json={'insumo_id': insumo.id, 'cantidad': cantidad_req},
            timeout=10,
        )
        data = resp.json()
        estado_resp = data.get('estado')
        detalle_resp = data.get('detalle', '')
        if estado_resp in {'disponible', 'parcial', 'no'}:
            consulta.estado = estado_resp
            consulta.respuesta = {'detalle': detalle_resp}
            consulta.save()
    except Exception as e:
        consulta.estado = 'error'
        consulta.respuesta = {'detalle': str(e)}
        consulta.save()


def _notificar_proveedor_email(oc):
    """Envía email de notificación al proveedor (fuera de atomic)."""
    try:
        from automatizacion.services import enviar_email_orden_compra_proveedor
        enviar_email_orden_compra_proveedor(oc)
    except Exception as e:
        logger.warning('enviar_email_orden_compra_proveedor falló: %s', e)


def _crear_propuesta_compra(insumo, cantidad_req, comentario_oc, motivo_trigger, criterios_pesos):
    """
    Crea (o actualiza) una CompraPropuesta:
      1. Recomienda proveedor óptimo.
      2. Dentro de atomic: crea OC + ConsultaStockProveedor + propuesta.
      3. Fuera de atomic: HTTP al proveedor + email.
    Retorna (proveedor, oc, consulta).
    """
    from django.db import transaction
    from automatizacion.models import CompraPropuesta, ConsultaStockProveedor
    from pedidos.models import OrdenCompra
    from automatizacion.api.services import ProveedorInteligenteService

    proveedor = ProveedorInteligenteService.recomendar_proveedor(insumo)
    with transaction.atomic():
        oc = OrdenCompra.objects.create(
            insumo=insumo,
            cantidad=cantidad_req,
            proveedor=proveedor,
            estado='sugerida',
            comentario=comentario_oc,
        )
        consulta = ConsultaStockProveedor.objects.create(
            proveedor=proveedor,
            insumo=insumo,
            cantidad=cantidad_req,
            estado='pendiente',
            respuesta={},
        )
        propuesta_existente = CompraPropuesta.objects.filter(
            insumo=insumo, consulta_stock__isnull=True
        ).order_by('-creada').first()
        if propuesta_existente:
            propuesta_existente.consulta_stock = consulta
            propuesta_existente.borrador_oc = oc
            propuesta_existente.proveedor_recomendado = proveedor
            propuesta_existente.estado = 'consultado'
            propuesta_existente.save()
        else:
            CompraPropuesta.objects.create(
                insumo=insumo,
                cantidad_requerida=cantidad_req,
                proveedor_recomendado=proveedor,
                pesos_usados=criterios_pesos,
                motivo_trigger=motivo_trigger,
                estado='consultado',
                borrador_oc=oc,
                consulta_stock=consulta,
            )
    # HTTP y email fuera del atomic
    _consultar_stock_http(proveedor, insumo, cantidad_req, consulta)
    _notificar_proveedor_email(oc)
    return proveedor, oc, consulta


@shared_task
def tarea_automatizacion_presupuestos_ponderada():
    """Detecta necesidades de compra y genera propuestas automáticas:
    - Cruza pedidos recientes y stock de insumos
    - Recomienda proveedor óptimo (precio, cumplimiento, incidencias, disponibilidad)
    - Genera borrador de Orden de Compra
    - Registra consulta de stock al proveedor
    """
    try:
        from decimal import Decimal
        from pedidos.services import calcular_consumo_pedido, verificar_stock_consumo
        from automatizacion.api.services import ProveedorInteligenteService
        from automatizacion.models import CompraPropuesta
        from insumos.models import Insumo

        CRITERIOS_PESOS = ProveedorInteligenteService._get_pesos()

        # 1) Revisar pedidos recientes (últimos 7 días, parametrizable)
        ventana_dias = int(Parametro.get('AUTOPRESUPUESTO_VENTANA_DIAS', 7))
        desde = timezone.now().date() - timedelta(days=ventana_dias)
        pedidos_recientes = Pedido.objects.select_related('cliente', 'estado').filter(fecha_pedido__gte=desde)

        propuestas_creadas = 0

        for pedido in pedidos_recientes:
            consumo = calcular_consumo_pedido(pedido)
            ok, faltantes = verificar_stock_consumo(consumo)
            if ok:
                continue
            for insumo_id, faltan in faltantes.items():
                try:
                    insumo = Insumo.objects.get(idInsumo=insumo_id)
                except Insumo.DoesNotExist:
                    continue
                cantidad_req = insumo.cantidad_compra_sugerida or int(Decimal(str(faltan)))
                _crear_propuesta_compra(
                    insumo=insumo,
                    cantidad_req=cantidad_req,
                    comentario_oc=f"Auto por pedido {pedido.id}: faltante {cantidad_req}",
                    motivo_trigger='pedido_mayor_stock',
                    criterios_pesos=CRITERIOS_PESOS,
                )
                propuestas_creadas += 1

        # 6) Revisar insumos bajo stock mínimo global
        stock_minimo = int(Parametro.get('STOCK_MINIMO_GLOBAL', 10))
        bajos = Insumo.objects.filter(stock__lte=stock_minimo, activo=True)
        for insumo in bajos:
            ya = CompraPropuesta.objects.filter(insumo=insumo, consulta_stock__isnull=False).exists()
            if ya:
                continue
            cantidad_req = insumo.cantidad_compra_sugerida or max(1, stock_minimo * 2)
            _crear_propuesta_compra(
                insumo=insumo,
                cantidad_req=cantidad_req,
                comentario_oc=f"Auto stock mínimo: sugerido {cantidad_req}",
                motivo_trigger='stock_minimo_vencido',
                criterios_pesos=CRITERIOS_PESOS,
            )
            propuestas_creadas += 1

        # 7) Auto-aceptación según parámetros si hay respuesta disponible y el proveedor cumple umbral
        auto_aprobar = bool(Parametro.get('AUTO_APROBAR_PROPUESTAS', False))
        aceptadas_auto = 0
        if auto_aprobar:
            umbral_score = float(Parametro.get('UMBRAL_SCORE_PROVEEDOR', 70))
            # Propuestas en estado consultado o con respuesta disponible
            from automatizacion.models import CompraPropuesta
            from automatizacion.models import ScoreProveedor
            propuestas = CompraPropuesta.objects.select_related('insumo', 'proveedor_recomendado', 'consulta_stock', 'borrador_oc')\
                .filter(estado__in=['consultado', 'respuesta_disponible'],
                        creada__gte=timezone.now() - timedelta(days=3))
            for p in propuestas:
                try:
                    consulta_ok = p.consulta_stock and p.consulta_stock.estado == 'disponible'
                    proveedor = p.proveedor_recomendado
                    score_ok = False
                    if proveedor:
                        sp = ScoreProveedor.objects.filter(proveedor=proveedor).first()
                        score_ok = (sp and float(sp.score or 0) >= umbral_score)
                    if consulta_ok and score_ok:
                        oc = p.borrador_oc
                        if oc:
                            oc.estado = 'confirmada'
                            oc.save()
                        insumo = p.insumo
                        if proveedor:
                            insumo.proveedor = proveedor
                        insumo.stock = (insumo.stock or 0) + int(p.cantidad_requerida or 0)
                        insumo.save(update_fields=['proveedor', 'stock'])
                        p.estado = 'aceptada'
                        p.decision = 'aceptar'
                        p.comentario_admin = 'Aceptada automáticamente por umbrales'
                        p.save()
                        aceptadas_auto += 1
                except Exception:
                    # seguir con las demás
                    pass

        # 8) Relleno: crear ConsultaStockProveedor para propuestas que aún no tienen ninguna
        huerfanas = CompraPropuesta.objects.filter(
            consulta_stock__isnull=True,
            proveedor_recomendado__isnull=False,
        ).select_related('insumo', 'proveedor_recomendado')
        rellenadas = 0
        for p in huerfanas:
            try:
                with transaction.atomic():
                    consulta = ConsultaStockProveedor.objects.create(
                        proveedor=p.proveedor_recomendado,
                        insumo=p.insumo,
                        cantidad=int(p.cantidad_requerida or 1),
                        estado='pendiente',
                        respuesta={}
                    )
                    p.consulta_stock = consulta
                    p.save(update_fields=['consulta_stock'])
                    rellenadas += 1
            except Exception:
                pass

        return (
            f"auto_presupuesto: {propuestas_creadas} propuestas generadas; "
            f"{aceptadas_auto} aceptadas automáticamente; "
            f"{rellenadas} consultas de stock rellenadas"
        )
    except Exception as e:
        return f"auto_presupuesto: error {e}"


@shared_task
def tarea_vencer_ofertas():
    """
    Cierra automáticamente las ofertas que no fueron respondidas antes de su fecha_expiracion.
    - Afecta solo estados 'pendiente' y 'enviada'.
    - Registra un AutomationLog por cada oferta vencida.
    - Notifica al staff sobre el total de ofertas vencidas.
    Se debe programar para ejecutarse diariamente (por ejemplo a las 00:00).
    """
    try:
        ahora = timezone.now()
        vencidas_qs = OfertaPropuesta.objects.filter(
            estado__in=['pendiente', 'enviada'],
            fecha_expiracion__lt=ahora,
        ).select_related('cliente')

        total = vencidas_qs.count()
        if total == 0:
            return 'vencer_ofertas: ninguna oferta vencida'

        vencidas_ids = list(vencidas_qs.values_list('id', flat=True))

        # Marcar como vencidas en bulk
        OfertaPropuesta.objects.filter(id__in=vencidas_ids).update(
            estado='vencida',
            fecha_validacion=ahora,
        )

        # Registrar log por cada una
        try:
            from automatizacion.models import AutomationLog
            logs = [
                AutomationLog(
                    evento='oferta_vencida',
                    descripcion=f'Oferta #{oid} vencida automáticamente',
                    datos={'oferta_id': oid},
                )
                for oid in vencidas_ids
            ]
            AutomationLog.objects.bulk_create(logs, ignore_conflicts=True)
        except Exception:
            pass

        # Notificar al staff
        try:
            from usuarios.models import Usuario, Notificacion
            mensaje = f'{total} oferta(s) vencieron sin respuesta del cliente y fueron cerradas automáticamente.'
            for u in Usuario.objects.filter(is_staff=True):
                Notificacion.objects.create(usuario=u, mensaje=mensaje)
        except Exception:
            pass

        return f'vencer_ofertas: {total} oferta(s) marcadas como vencidas'
    except Exception as e:
        return f'vencer_ofertas: error {e}'
