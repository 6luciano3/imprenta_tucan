from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from automatizacion.models import ScoreProveedor, OfertaPropuesta
import requests
from configuracion.models import Parametro
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
        for insumo in Insumo.objects.filter(activo=True):
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
        engine = ProveedorInteligenteEngine()
        count = 0
        for proveedor in Proveedor.objects.filter(activo=True):
            score = engine.calcular_score(proveedor, insumo=None)
            ScoreProveedor.objects.update_or_create(
                proveedor=proveedor,
                defaults={'score': score},
            )
            count += 1
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
    # Emitir alertas según reglas/umbrales (placeholder)
    try:
        return "alertas_retraso: ejecutado (placeholder)"
    except Exception as e:
        return f"alertas_retraso: error {e}"


CANTIDADES_COMPRA = {
    'IN-001': 2, 'IN-002': 1, 'IN-003': 1, 'IN-004': 1,
    'IN-042': 1, 'IN-043': 1,
    'TIN-NEGR': 2, 'TIN-CYAN': 1, 'TIN-MAGE': 1, 'TIN-AMAR': 1,
    'IN-018': 1, 'IN-019': 1, 'IN-020': 2, 'BAR-UV-LIQ': 2, 'IN-118': 1,
    'IN-021': 1000, 'IN-022': 500, 'IN-023': 1000, 'IN-024': 5000, 'IN-025': 5000,
    'IN-055': 500, 'IN-056': 1000, 'IN-057': 500, 'IN-071': 2000, 'IN-072': 1000,
    'IN-100': 1000, 'IN-103': 1000, 'IN-104': 500, 'IN-105': 500,
    'IN-106': 5000, 'IN-107': 2000, 'IN-108': 500,
    'PAP-AUT-CON': 2000, 'PAP-ILU-115': 1000, 'PAP-ILU-130': 1000,
    'PAP-ILU-150': 1000, 'PAP-OBR-080': 5000, 'PAP001': 1000,
    'CAR-ILU-250': 500, 'CAR-ILU-300': 500, 'CAR-ILU-350': 500,
    'CAR-GRI-150': 200, 'CAR-GRI-200': 200, 'IN-110': 200, 'IN-111': 200, 'IN-112': 300,
    'IN-101': 1, 'IN-102': 1, 'LAM-BRI-32': 1, 'LAM-MAT-32': 1,
    'PLA-ALU-STD': 50,
    'ENC-ADH-BLO': 5, 'ENC-ESP-MET': 10, 'ENC-GRA-IND': 5, 'ENC-HOT-MEL': 3,
    'IN-113': 3, 'IN-114': 5, 'IN-115': 10, 'IN-116': 10, 'IN-117': 5, 'IN-109': 2,
}

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
        from django.db import transaction
        from pedidos.services import calcular_consumo_pedido, verificar_stock_consumo
        from automatizacion.api.services import ProveedorInteligenteService
        CRITERIOS_PESOS = ProveedorInteligenteService._get_pesos()
        from automatizacion.models import CompraPropuesta, ConsultaStockProveedor
        from pedidos.models import OrdenCompra
        from insumos.models import Insumo

        # 1) Revisar pedidos recientes (últimos 7 días) y/o parametrizable
        ventana_dias = int(Parametro.get('AUTOPRESUPUESTO_VENTANA_DIAS', 7))
        desde = timezone.now().date() - timedelta(days=ventana_dias)
        pedidos_recientes = Pedido.objects.filter(fecha_pedido__gte=desde).select_related('producto')

        propuestas_creadas = 0

        for pedido in pedidos_recientes:
            consumo = calcular_consumo_pedido(pedido)
            ok, faltantes = verificar_stock_consumo(consumo)
            if ok:
                continue  # no hay faltante
            for insumo_id, faltan in faltantes.items():
                try:
                    insumo = Insumo.objects.get(idInsumo=insumo_id)
                except Insumo.DoesNotExist:
                    continue
                cantidad_req = CANTIDADES_COMPRA.get(insumo.codigo, int(Decimal(str(faltan))))
                # 2) Recomendar proveedor óptimo
                proveedor = ProveedorInteligenteService.recomendar_proveedor(insumo)
                # 3) Generar borrador de Orden de Compra
                with transaction.atomic():
                    oc = OrdenCompra.objects.create(
                        insumo=insumo,
                        cantidad=cantidad_req,
                        proveedor=proveedor,
                        estado='sugerida',
                        comentario=f"Auto por pedido {pedido.id}: faltante {cantidad_req}"
                    )
                    # 4) Registrar consulta de stock
                    consulta = ConsultaStockProveedor.objects.create(
                        proveedor=proveedor,
                        insumo=insumo,
                        cantidad=cantidad_req,
                        estado='pendiente',
                        respuesta={}
                    )
                    # --- INTEGRACIÓN REAL: consulta HTTP si el proveedor tiene api_stock_url ---
                    if proveedor.api_stock_url:
                        try:
                            resp = requests.post(
                                proveedor.api_stock_url,
                                json={
                                    'insumo_id': insumo.id,
                                    'cantidad': cantidad_req
                                },
                                timeout=10
                            )
                            data = resp.json()
                            estado = data.get('estado')  # 'disponible', 'parcial', 'no', etc.
                            detalle = data.get('detalle', '')
                            if estado in {'disponible', 'parcial', 'no'}:
                                consulta.estado = estado
                                consulta.respuesta = {'detalle': detalle}
                                consulta.save()
                        except Exception as e:
                            consulta.estado = 'error'
                            consulta.respuesta = {'detalle': str(e)}
                            consulta.save()
                    # 5) Crear propuesta consolidada
                    CompraPropuesta.objects.create(
                        insumo=insumo,
                        cantidad_requerida=cantidad_req,
                        proveedor_recomendado=proveedor,
                        pesos_usados=CRITERIOS_PESOS,
                        motivo_trigger='pedido_mayor_stock',
                        estado='consultado',
                        borrador_oc=oc,
                        consulta_stock=consulta,
                    )
                    propuestas_creadas += 1
                    # 6) Notificar al proveedor por email
                    try:
                        from automatizacion.services import enviar_email_orden_compra_proveedor
                        enviar_email_orden_compra_proveedor(oc)
                    except Exception:
                        pass

        # 6) Revisar insumos bajo stock mínimo global
        stock_minimo = int(Parametro.get('STOCK_MINIMO_GLOBAL', 10))
        bajos = Insumo.objects.filter(stock__lte=stock_minimo, activo=True)
        for insumo in bajos:
            # evitar duplicar si ya hay propuesta reciente del mismo insumo
            ya = CompraPropuesta.objects.filter(insumo=insumo, creada__gte=timezone.now()-timedelta(days=3)).exists()
            if ya:
                continue
            proveedor = ProveedorInteligenteService.recomendar_proveedor(insumo)
            cantidad_req = CANTIDADES_COMPRA.get(insumo.codigo, max(1, stock_minimo * 2))
            with transaction.atomic():
                oc = OrdenCompra.objects.create(
                    insumo=insumo,
                    cantidad=cantidad_req,
                    proveedor=proveedor,
                    estado='sugerida',
                    comentario=f"Auto stock mínimo: sugerido {cantidad_req}"
                )
                consulta = ConsultaStockProveedor.objects.create(
                    proveedor=proveedor,
                    insumo=insumo,
                    cantidad=cantidad_req,
                    estado='pendiente',
                    respuesta={}
                )
                # --- INTEGRACIÓN REAL: consulta HTTP si el proveedor tiene api_stock_url ---
                if proveedor.api_stock_url:
                    try:
                        resp = requests.post(
                            proveedor.api_stock_url,
                            json={
                                'insumo_id': insumo.id,
                                'cantidad': cantidad_req
                            },
                            timeout=10
                        )
                        data = resp.json()
                        estado = data.get('estado')
                        detalle = data.get('detalle', '')
                        if estado in {'disponible', 'parcial', 'no'}:
                            consulta.estado = estado
                            consulta.respuesta = {'detalle': detalle}
                            consulta.save()
                    except Exception as e:
                        consulta.estado = 'error'
                        consulta.respuesta = {'detalle': str(e)}
                        consulta.save()
                CompraPropuesta.objects.create(
                    insumo=insumo,
                    cantidad_requerida=cantidad_req,
                    proveedor_recomendado=proveedor,
                    pesos_usados=CRITERIOS_PESOS,
                    motivo_trigger='stock_minimo_vencido',
                    estado='consultado',
                    borrador_oc=oc,
                    consulta_stock=consulta,
                )
                propuestas_creadas += 1
                # Notificar al proveedor por email
                try:
                    from automatizacion.services import enviar_email_orden_compra_proveedor
                    enviar_email_orden_compra_proveedor(oc)
                except Exception:
                    pass

        # 7) Auto-aceptación según parámetros si hay respuesta disponible y el proveedor cumple umbral
        auto_aprobar = bool(Parametro.get('AUTO_APROBAR_PROPUESTAS', False))
        aceptadas_auto = 0
        if auto_aprobar:
            umbral_score = float(Parametro.get('UMBRAL_SCORE_PROVEEDOR', 70))
            # Propuestas en estado consultado o con respuesta disponible
            from automatizacion.models import CompraPropuesta
            from automatizacion.models import ScoreProveedor
            propuestas = CompraPropuesta.objects.select_related('insumo', 'proveedor_recomendado', 'consulta_stock', 'borrador_oc')\
                .filter(estado__in=['consultado', 'respuesta_disponible'])
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

        return f"auto_presupuesto: {propuestas_creadas} propuestas generadas; {aceptadas_auto} aceptadas automáticamente"
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
