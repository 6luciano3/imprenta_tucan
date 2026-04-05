import logging
from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from automatizacion.models import ScoreProveedor, OfertaPropuesta
import requests
from configuracion.models import Parametro, GrupoParametro
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
    PI - Prediccion de demanda de insumos directos.
    Genera ProyeccionInsumo para el proximo periodo usando media movil ponderada.
    Solo procesa insumos de tipo directo.
    """
    try:
        from insumos.models import Insumo, ProyeccionInsumo, predecir_demanda_media_movil
        from automatizacion.models import ScoreProveedor
        from django.utils import timezone
        from datetime import timedelta

        # Calcular periodo actual y siguiente
        now = timezone.now()
        if now.month == 12:
            periodo_siguiente = f'{now.year + 1}-01'
        else:
            periodo_siguiente = f'{now.year}-{now.month + 1:02d}'

        from core.motor.config import MotorConfig
        meses = MotorConfig.get('PROYECCION_MESES', cast=int) or 3

        insumos = Insumo.objects.filter(activo=True, tipo='directo')
        procesados = 0
        urgentes = 0

        for insumo in insumos:
            try:
                cantidad_proyectada = predecir_demanda_media_movil(insumo, periodo_siguiente, meses=meses) or 0
                if cantidad_proyectada <= 0:
                    # Si no hay historial usar stock_minimo * 2 como base
                    cantidad_proyectada = int(insumo.stock_minimo_sugerido or 0) * 2 or 10

                # Proveedor sugerido: el de mayor score
                score = ScoreProveedor.objects.filter(
                    proveedor__activo=True
                ).exclude(
                    proveedor__email__endswith='.local'
                ).order_by('-score').first()
                proveedor_sugerido = score.proveedor if score else None

                # Crear o actualizar proyeccion.
                # Si ya existe y está en estado terminal (aceptada/validada/rechazada),
                # actualizar solo la cantidad y proveedor sin resetear el estado.
                ESTADOS_TERMINALES = {'aceptada', 'validada', 'rechazada'}
                existente = ProyeccionInsumo.objects.filter(
                    insumo=insumo, periodo=periodo_siguiente
                ).first()

                if existente and existente.estado in ESTADOS_TERMINALES:
                    # Solo actualizar datos de cantidad; no tocar el estado
                    existente.cantidad_proyectada = int(cantidad_proyectada)
                    existente.proveedor_sugerido = proveedor_sugerido
                    existente.fecha_generacion = now
                    existente.save(update_fields=[
                        'cantidad_proyectada', 'proveedor_sugerido', 'fecha_generacion'
                    ])
                    proj = existente
                    created = False
                else:
                    proj, created = ProyeccionInsumo.objects.update_or_create(
                        insumo=insumo,
                        periodo=periodo_siguiente,
                        defaults={
                            'cantidad_proyectada': int(cantidad_proyectada),
                            'proveedor_sugerido': proveedor_sugerido,
                            'fecha_generacion': now,
                            'estado': 'pendiente',
                        }
                    )
                procesados += 1

                # Detectar urgencia: stock actual menor que proyeccion
                stock_actual = int(insumo.stock or 0)
                if stock_actual < int(cantidad_proyectada):
                    urgentes += 1

            except Exception as e:
                logger.warning(f'tarea_prediccion_demanda: error en insumo {insumo.nombre}: {e}')

        # Notificar al admin con detalle de urgentes
        try:
            from django.conf import settings as _s
            from core.notifications.engine import enviar_notificacion
            from usuarios.models import Notificacion
            from django.contrib.auth import get_user_model
            admin_email = getattr(_s, 'EMAIL_HOST_USER', '')
            # Obtener insumos urgentes para el reporte
            urgentes_lista = ProyeccionInsumo.objects.filter(
                periodo=periodo_siguiente,
                estado='pendiente'
            ).select_related('insumo').order_by('insumo__stock')
            urgentes_detalle = '\n'.join([
                f'- {p.insumo.nombre}: stock={p.insumo.stock}, proyectado={p.cantidad_proyectada}'
                for p in urgentes_lista[:10]
            ])
            asunto = f'[Imprenta Tucan] Prediccion {periodo_siguiente}: {procesados} proyecciones ({urgentes} urgentes)'
            mensaje = (
                f'Se generaron {procesados} proyecciones de demanda para {periodo_siguiente}.\n\n'
                f'Insumos con stock insuficiente ({urgentes}):\n{urgentes_detalle}\n\n'
                f'Ingrese al panel para revisar y validar las proyecciones:\n'
                f'/automatizacion/prediccion/'
            )
            # Notificacion interna a staff
            for u in get_user_model().objects.filter(is_staff=True):
                Notificacion.objects.create(usuario=u, mensaje=f'Prediccion {periodo_siguiente}: {procesados} proyecciones, {urgentes} urgentes.')
            if admin_email:
                enviar_notificacion(
                    destinatario=admin_email,
                    canal='email',
                    asunto=asunto,
                    mensaje=mensaje,
                )
        except Exception as e:
            logger.warning(f'tarea_prediccion_demanda: error notificando admin: {e}')

        return f"prediccion_demanda: {procesados} insumos directos proyectados para {periodo_siguiente} ({urgentes} urgentes)"
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



# Tarea que se ejecuta cada hora y decide si corresponde generar ofertas
@shared_task
def tarea_verificar_generacion_ofertas():
    """
    Verifica si corresponde generar ofertas según el intervalo configurado.
    Crea el parámetro OFERTAS_INTERVALO_HORAS si no existe.
    """
    from django.utils import timezone
    from automatizacion.models import AutomationLog
    from core.ai_ml.ofertas import generar_ofertas_segmentadas
    from django.db import transaction

    # Buscar o crear parámetro
    grupo = GrupoParametro.objects.filter(codigo="AUTOMATIZACION").first()
    if not grupo:
        grupo = GrupoParametro.objects.first()
    intervalo = Parametro.get("OFERTAS_INTERVALO_HORAS")
    if intervalo is None:
        Parametro.set(
            "OFERTAS_INTERVALO_HORAS",
            24,
            tipo=Parametro.TIPO_INT,
            grupo=grupo,
            nombre="Intervalo de generación de ofertas (horas)",
            descripcion="Frecuencia en horas para la generación automática de ofertas.",
        )
        intervalo = 24
    try:
        intervalo = int(intervalo)
    except Exception:
        intervalo = 24

    # Buscar última ejecución
    ultimo_log = AutomationLog.objects.filter(evento="ofertas_generadas").order_by("-fecha").first()
    ahora = timezone.now()
    if ultimo_log:
        delta = ahora - ultimo_log.fecha
        horas = delta.total_seconds() / 3600
        if horas < intervalo:
            return f"No corresponde generar ofertas: solo han pasado {horas:.1f}h (intervalo={intervalo}h)"

    # Generar ofertas
    resultado = generar_ofertas_segmentadas()
    count = resultado['generadas']
    periodo = resultado['periodo']
    try:
        AutomationLog.objects.create(
            evento='ofertas_generadas',
            descripcion=f'{count} ofertas generadas automáticamente (período: {periodo}).',
            datos={'generadas': count, 'periodo': periodo},
        )
    except Exception:
        pass
    # Auto-enviar segun umbral de score
    try:
        from automatizacion.services import enviar_oferta_email
        umbral = int(Parametro.get('UMBRAL_AUTO_ENVIO_SCORE', 0))
        pendientes = OfertaPropuesta.objects.filter(estado='pendiente').select_related('cliente')
        enviadas_auto = 0
        for oferta in pendientes:
            score = oferta.score_al_generar or 0
            if score >= umbral:
                ok, _ = enviar_oferta_email(oferta, force=True)
                if ok:
                    oferta.estado = 'enviada'
                    oferta.fecha_validacion = ahora
                    oferta.save(update_fields=['estado', 'fecha_validacion'])
                    enviadas_auto += 1
        if enviadas_auto:
            AutomationLog.objects.create(
                evento='ofertas_enviadas_auto',
                descripcion=f'{enviadas_auto} ofertas enviadas automaticamente (umbral score={umbral}).',
                datos={'enviadas': enviadas_auto, 'umbral': umbral},
            )
    except Exception as e:
        logger.warning('Auto-envio de ofertas fallo: %s', e)
        enviadas_auto = 0

    return f"generar_ofertas: {count} propuestas generadas, {enviadas_auto} enviadas ({periodo})"


@shared_task
def tarea_expirar_ofertas():
    """Marca como 'vencidas' todas las ofertas enviadas/pendientes cuya fecha_expiracion ya pasó."""
    try:
        from automatizacion.models import OfertaPropuesta, AutomationLog
        expiradas = OfertaPropuesta.objects.filter(
            estado__in=['pendiente', 'enviada'],
            fecha_expiracion__lt=timezone.now(),
        )
        count = expiradas.count()
        expiradas.update(estado='vencida')
        if count:
            AutomationLog.objects.create(
                evento='ofertas_expiradas',
                descripcion=f'{count} ofertas marcadas como vencidas automáticamente.',
                datos={'expiradas': count},
            )
        return f"expirar_ofertas: {count} ofertas vencidas"
    except Exception as e:
        return f"expirar_ofertas: error {e}"

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




def _enviar_cotizacion_multiples_proveedores(insumo, cantidad_req, comentario, motivo_trigger, criterios_pesos, auto_aprobar=True):
    """
    PROCESO INTELIGENTE: Envía solicitud de cotización automáticamente a los top N proveedores
    con email real (no .local). Crea una OrdenCompra por cada proveedor.
    
    Si auto_aprobar=True (por defecto):
    - Aprueba automáticamente la orden (estado='confirmada')
    - Envía email automáticamente al proveedor
    
    Notifica al admin con el resumen de envios.
    """
    from automatizacion.models import CompraPropuesta, ConsultaStockProveedor, ScoreProveedor
    from pedidos.models import OrdenCompra
    from automatizacion.services import enviar_email_orden_compra_proveedor
    from proveedores.models import Proveedor
    from django.conf import settings as dj_settings
    from core.notifications.engine import enviar_notificacion

    try:
        top_n = int(Parametro.get('TOP_N_PROVEEDORES_COTIZACION', 5))
    except Exception:
        top_n = 5

    # PROCESO INTELIGENTE: Usar proveedor real para demostración
    EMAIL_PROVEEDOR_REAL = 'serigrafiaplusrawson@gmail.com'
    proveedor_real = Proveedor.objects.filter(email=EMAIL_PROVEEDOR_REAL, activo=True).first()
    if proveedor_real:
        proveedores_seleccionados = [proveedor_real]
    else:
        # Fallback: Top N proveedores activos con email real (excluir .local)
        scores = (
            ScoreProveedor.objects
            .select_related('proveedor')
            .filter(proveedor__activo=True)
            .exclude(proveedor__email__isnull=True)
            .exclude(proveedor__email='')
            .exclude(proveedor__email__endswith='.local')
            .order_by('-score')[:top_n]
        )
        proveedores_seleccionados = [s.proveedor for s in scores]
    
    if not proveedores_seleccionados:
        logger.warning('_enviar_cotizacion_multiples_proveedores: sin proveedores con email real')
        return 0

    enviados = 0
    nombres_enviados = []

    for proveedor in proveedores_seleccionados:
        try:
            from django.db import transaction
            from django.utils import timezone
            with transaction.atomic():
                # PROCESO INTELIGENTE: Aprobar automáticamente si está habilitado
                estado_inicial = 'confirmada' if auto_aprobar else 'sugerida'
                oc = OrdenCompra.objects.create(
                    insumo=insumo,
                    cantidad=cantidad_req,
                    proveedor=proveedor,
                    estado=estado_inicial,
                    comentario=comentario + (' [AUTO-APROBADO]' if auto_aprobar else ''),
                )
                consulta = ConsultaStockProveedor.objects.create(
                    proveedor=proveedor,
                    insumo=insumo,
                    cantidad=cantidad_req,
                    estado='pendiente',
                    respuesta={},
                )
                # PROCESO INTELIGENTE: Cambiar estado según auto_aprobar
                estado_propuesta = 'aprobada' if auto_aprobar else 'consultado'
                CompraPropuesta.objects.create(
                    insumo=insumo,
                    cantidad_requerida=cantidad_req,
                    proveedor_recomendado=proveedor,
                    pesos_usados=criterios_pesos,
                    motivo_trigger=motivo_trigger,
                    estado=estado_propuesta,
                    borrador_oc=oc,
                    consulta_stock=consulta,
                )
            # Enviar email fuera del atomic
            ok, err = enviar_email_orden_compra_proveedor(oc)
            if ok:
                enviados += 1
                nombres_enviados.append(proveedor.nombre)
                logger.info('Cotizacion enviada a %s para insumo %s', proveedor.email, insumo.nombre)
            else:
                logger.warning('Error enviando cotizacion a %s: %s', proveedor.email, err)
        except Exception as e:
            logger.error('Error creando OC para proveedor %s: %s', proveedor.nombre, e)

    # Notificar al admin con resumen
    if enviados > 0:
        try:
            from usuarios.models import Usuario, Notificacion
            from django.conf import settings as _s
            resumen = (
                f'Solicitud de cotizacion enviada automaticamente para "{insumo.nombre}" '
                f'({cantidad_req} unidades) a {enviados} proveedor(es): '
                f'{", ".join(nombres_enviados)}. '
                f'Revisa las respuestas en el panel de Compras.'
            )
            for u in Usuario.objects.filter(is_staff=True):
                Notificacion.objects.create(usuario=u, mensaje=resumen)
            # Email al admin
            managers = getattr(_s, 'MANAGERS', [])
            admin_email = managers[0][1] if managers else getattr(_s, 'EMAIL_HOST_USER', '')
            if admin_email:
                enviar_notificacion(
                    destinatario=admin_email,
                    canal='email',
                    asunto=f'Cotizacion automatica enviada: {insumo.nombre}',
                    mensaje=resumen,
                )
        except Exception as e:
            logger.warning('Error notificando admin sobre cotizacion: %s', e)

    return enviados

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
        from django.utils import timezone
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
                _enviar_cotizacion_multiples_proveedores(
                    insumo=insumo,
                    cantidad_req=cantidad_req,
                    comentario=f"Solicitud de cotizacion automatica por pedido {pedido.id}: faltante {cantidad_req} unidades",
                    motivo_trigger='pedido_mayor_stock',
                    criterios_pesos=CRITERIOS_PESOS,
                )
                propuestas_creadas += 1

        # 6) Agrupar insumos directos bajo stock minimo y enviar UNA SolicitudCotizacion por proveedor
        from automatizacion.models import ScoreProveedor
        from automatizacion.services import enviar_solicitud_cotizacion
        stock_minimo = int(Parametro.get('STOCK_MINIMO_GLOBAL', 10))
        top_n = int(Parametro.get('TOP_N_PROVEEDORES_COTIZACION', 5))
        hace_7dias = timezone.now() - timedelta(days=7)
        bajos = Insumo.objects.filter(stock__lte=stock_minimo, activo=True, tipo='directo')
        insumos_libres = []
        for insumo in bajos:
            ya = CompraPropuesta.objects.filter(
                insumo=insumo,
                consulta_stock__isnull=False,
                creada__gte=hace_7dias
            ).exists()
            if not ya:
                cantidad_req = insumo.cantidad_compra_sugerida or max(1, stock_minimo * 2)
                insumos_libres.append((insumo, cantidad_req))
        if insumos_libres:
            # PROCESO INTELIGENTE: Usar proveedor real para demostración
            EMAIL_PROVEEDOR_REAL = 'serigrafiaplusrawson@gmail.com'
            proveedor_real = Proveedor.objects.filter(email=EMAIL_PROVEEDOR_REAL, activo=True).first()
            
            if proveedor_real:
                # Usar el proveedor real
                try:
                    sc, ok, err = enviar_solicitud_cotizacion(
                        proveedor=proveedor_real,
                        insumos_cantidades=insumos_libres,
                        comentario='Solicitud automatica por stock minimo detectado [PROCESO INTELIGENTE]',
                    )
                    if ok:
                        propuestas_creadas += 1
                        logger.info('SC-%s enviada a proveedor real %s con %s insumos', sc.id, proveedor_real.email, len(insumos_libres))
                        
                        # Enviar copia a emails de demostración
                        EMAILS_DEMOSTRACION = ['bookdesignpdas@yahoo.com.ar', '6luciano10@gmail.com']
                        from core.notifications.engine import enviar_notificacion
                        for email_demo in EMAILS_DEMOSTRACION:
                            try:
                                enviar_notificacion(
                                    destinatario=email_demo,
                                    mensaje=f'COTIZACIÓN ENVIADA: SC-{sc.id} a {proveedor_real.nombre}\nInsumos: {len(insumos_libres)}',
                                    canal='email',
                                    asunto=f'[COPIA] Cotización SC-{sc.id} - {proveedor_real.nombre}',
                                    metadata={'solicitud_cotizacion_id': sc.id, 'copia_demo': True},
                                )
                            except Exception:
                                pass
                    else:
                        logger.warning('Error enviando SC a %s: %s', proveedor_real.email, err)
                except Exception as e:
                    logger.error('Error creando SC para proveedor %s: %s', proveedor_real.nombre, e)
            else:
                # Fallback: usar proveedores con mejor score
                scores = (
                    ScoreProveedor.objects
                    .select_related('proveedor')
                    .filter(proveedor__activo=True)
                    .exclude(proveedor__email__isnull=True)
                    .exclude(proveedor__email='')
                    .exclude(proveedor__email__endswith='.local')
                    .order_by('-score')[:top_n]
                )
                proveedores = [s.proveedor for s in scores]
                for proveedor in proveedores:
                    try:
                        sc, ok, err = enviar_solicitud_cotizacion(
                            proveedor=proveedor,
                            insumos_cantidades=insumos_libres,
                            comentario='Solicitud automatica por stock minimo detectado',
                        )
                        if ok:
                            propuestas_creadas += 1
                            logger.info('SC-%s enviada a %s con %s insumos', sc.id, proveedor.email, len(insumos_libres))
                        else:
                            logger.warning('Error enviando SC a %s: %s', proveedor.email, err)
                    except Exception as e:
                        logger.error('Error creando SC para proveedor %s: %s', proveedor.nombre, e)

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
                        # Remito automatico generado por App Compras
                        try:
                            from compras.models import Remito, DetalleRemito, EstadoCompra, OrdenCompra
                            from django.utils import timezone
                            estado_recibida, _ = EstadoCompra.objects.get_or_create(nombre='Recibida')
                            remito = Remito.objects.create(
                                proveedor=insumo.proveedor,
                                numero=f'AUTO-{p.pk:06d}',
                                fecha=timezone.now().date(),
                                observaciones=f'Automatico CompraPropuesta #{p.pk}',
                            )
                            cantidad = int(p.cantidad_requerida or 0)
                            DetalleRemito.objects.create(remito=remito, insumo=insumo, cantidad=cantidad)
                            insumo.stock = (insumo.stock or 0) + cantidad
                            insumo.save(update_fields=['stock', 'updated_at'])
                        except Exception as e_r:
                            insumo.stock = (insumo.stock or 0) + int(p.cantidad_requerida or 0)
                            insumo.save(update_fields=['stock'])
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

        # Notificar al cliente por email
        try:
            from core.notifications.engine import enviar_notificacion
            from automatizacion.models import OfertaPropuesta as OP
            for oferta in OP.objects.filter(id__in=vencidas_ids).select_related('cliente'):
                cliente = oferta.cliente
                if not getattr(cliente, 'email_verificado', False):
                    continue
                enviar_notificacion(
                    destinatario=cliente.email,
                    canal='email',
                    asunto=f'Tu oferta "{oferta.titulo}" ha vencido',
                    mensaje=(
                        f'Hola {cliente.nombre}, '
                        f'la oferta "{oferta.titulo}" que preparamos especialmente para vos '
                        f'ha vencido sin ser respondida. '
                        f'Comunicate con nosotros si queres que generemos una nueva propuesta.'
                    ),
                )
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


@shared_task
def tarea_prediccion_demanda_semanal():
    """
    Disparador semanal (cada domingo) para ejecutar la prediccion de demanda
    y notificar al administrador con el reporte de proyecciones.
    """
    return tarea_prediccion_demanda()


@shared_task
def tarea_recordatorio_presupuestos():
    """
    Envía recordatorios automáticos a clientes cuando sus presupuestos están próximos a vencer.
    Busca presupuestos con validez = hoy + DIAS_ANTES_VENCIMIENTO (default 3 días),
    cuyo estado de respuesta sea 'pendiente'.
    """
    from presupuestos.models import Presupuesto
    from django.utils import timezone
    from datetime import timedelta
    from automatizacion.models import AutomationLog
    from django.conf import settings
    from configuracion.models import Parametro

    try:
        dias_antes = int(Parametro.get('PRESUPUESTO_DIAS_RECORDATORIO', 3))
    except Exception as e:
        logger.warning('Error leyendo PRESUPUESTO_DIAS_RECORDATORIO: %s. Usando default 3 días.', e)
        dias_antes = 3

    fecha_limite = timezone.now().date() + timedelta(days=dias_antes)
    fecha_hoy = timezone.now().date()

    presupuestos = Presupuesto.objects.filter(
        respuesta_cliente='pendiente',
        validez__gte=fecha_hoy,
        validez__lte=fecha_limite,
        estado='Activo',
    ).select_related('cliente')

    total = presupuestos.count()
    if total == 0:
        return 'recordatorio_presupuestos: no hay presupuestos próximos a vencer'

    enviados = 0
    errores = 0

    for presupuesto in presupuestos:
        try:
            cliente = presupuesto.cliente

            # Validar email: debe existir y estar verificado
            if not cliente.email:
                logger.warning('Recordatorio omitido para presupuesto %s: cliente sin email', presupuesto.numero)
                errores += 1
                continue
            if not getattr(cliente, 'email_verificado', True):
                logger.warning('Recordatorio omitido para presupuesto %s: email no verificado', presupuesto.numero)
                errores += 1
                continue

            # Deduplicación: no enviar más de una vez por día
            if presupuesto.recordatorio_enviado_fecha == fecha_hoy:
                logger.info('Recordatorio ya enviado hoy para presupuesto %s, omitiendo', presupuesto.numero)
                continue

            link_presupuesto = f"{getattr(settings, 'BASE_URL', 'http://localhost:8000')}/presupuestos/respuesta/{presupuesto.token}/"

            dias_restantes = (presupuesto.validez - fecha_hoy).days
            mensaje_texto = (
                f"Hola {cliente.nombre},\n\n"
                f"Te recordamos que tu presupuesto #{presupuesto.numero} vence "
                f"el {presupuesto.validez.strftime('%d/%m/%Y')} "
                f"({'hoy' if dias_restantes == 0 else f'en {dias_restantes} día/s'}).\n\n"
                f"Total: ${presupuesto.total}\n\n"
                f"Podés verlo, aceptarlo o rechazarlo aquí:\n{link_presupuesto}\n\n"
                f"Saludos,\nEquipo Imprenta Tucán"
            )

            try:
                from django.template.loader import render_to_string
                html_body = render_to_string('presupuestos/email/recordatorio.html', {
                    'cliente': cliente,
                    'presupuesto': presupuesto,
                    'link': link_presupuesto,
                    'dias_restantes': dias_restantes,
                })
            except Exception:
                html_body = None

            try:
                from core.notifications.engine import enviar_notificacion
                enviar_notificacion(
                    destinatario=cliente.email,
                    canal='email',
                    asunto=f'Recordatorio: Tu presupuesto #{presupuesto.numero} vence pronto',
                    mensaje=mensaje_texto,
                    html=html_body,
                )
                presupuesto.recordatorio_enviado_fecha = fecha_hoy
                presupuesto.save(update_fields=['recordatorio_enviado_fecha'])
                enviados += 1
            except Exception as e:
                logger.warning('Error enviando recordatorio presupuesto %s: %s', presupuesto.numero, e)
                errores += 1

        except Exception as e:
            logger.warning('Error procesando presupuesto %s: %s', presupuesto.numero, e)
            errores += 1

    AutomationLog.objects.create(
        evento='recordatorio_presupuestos',
        descripcion=f'{enviados} recordatorios enviados, {errores} errores (presupuestos próximos a vencer: {total})',
        datos={'enviados': enviados, 'errores': errores, 'total_presupuestos': total},
    )

    return f'recordatorio_presupuestos: {enviados} enviados, {errores} errores de {total} presupuestos'


@shared_task
def tarea_clientes_inactivos():
    """
    Envía notificaciones automáticas a clientes que no han realizado pedidos en X días.
    Busca clientes cuyo último pedido tenga más de DIAS_INACTIVIDAD días (default 90).
    Envía email de reactivación con tracking de apertura, clicks y respuestas.
    """
    import uuid
    from clientes.models import Cliente
    from pedidos.models import Pedido
    from django.utils import timezone
    from datetime import timedelta
    from automatizacion.models import AutomationLog, EmailTracking
    from django.conf import settings
    from django.template.loader import render_to_string

    try:
        dias_inactividad = int(Parametro.get('CLIENTE_DIAS_INACTIVIDAD', 90))
    except Exception:
        dias_inactividad = 90

    fecha_limite = timezone.now().date() - timedelta(days=dias_inactividad)

    clientes_activos = Cliente.objects.filter(estado='Activo').values_list('id', flat=True)
    
    clientes_con_pedidos_recientes = Pedido.objects.filter(
        cliente__in=clientes_activos,
        fecha_pedido__gt=fecha_limite
    ).values_list('cliente_id', flat=True).distinct()

    clientes_inactivos = Cliente.objects.filter(
        estado='Activo'
    ).exclude(
        id__in=clientes_con_pedidos_recientes
    )

    total = clientes_inactivos.count()
    if total == 0:
        return 'clientes_inactivos: no hay clientes inactivos'

    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    email_pedido = getattr(settings, 'EMAIL_HOST_USER', 'info@imprentaucan.com.ar')
    reply_to = f"respuestas-{dias_inactividad}@imprentaucan.com.ar"

    enviados = 0
    errores = 0

    for cliente in clientes_inactivos:
        try:
            if not cliente.email:
                errores += 1
                continue

            ultimo_pedido = Pedido.objects.filter(cliente=cliente).order_by('-fecha_pedido').first()
            dias_sin_pedido = 0
            if ultimo_pedido:
                dias_sin_pedido = (timezone.now().date() - ultimo_pedido.fecha_pedido).days

            token = uuid.uuid4().hex
            
            tracking_url = f"{base_url}/api/tracking/open/{token}/"
            confirm_url = f"{base_url}/api/tracking/click/{token}/"
            
            pixel_tracking = f'<img src="{tracking_url}" width="1" height="1" alt="" />'
            
            mensaje_html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: #1e40af; color: white; padding: 20px; text-align: center;">
                    <h1>¡Te extrañamos en Imprenta Tucán!</h1>
                </div>
                <div style="padding: 20px;">
                    <p>Hola <strong>{cliente.nombre}</strong>,</p>
                    
                    <p>¡Te extrañamos! Han pasado <strong>{dias_sin_pedido} días</strong> desde tu último pedido.</p>
                    
                    <p>Queremos ofrecerte un <strong>descuento especial del 10%</strong> en tu próxima orden 
                    como agradecimiento por tu preferencia.</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{confirm_url}" style="background: #16a34a; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                            Confirmar que recibí este email
                        </a>
                    </div>
                    
                    <h3>Nuestros servicios:</h3>
                    <ul>
                        <li>Tarjetas de presentación</li>
                        <li>Volantes y folletos</li>
                        <li>Banners y cartelería</li>
                        <li>Impresión de libros y manuales</li>
                    </ul>
                    
                    <p>¿Querés Respondenos a este email con tus consultas o pedidos.</p>
                    
                    <p style="margin-top: 30px;">¡Te esperamos de vuelta!</p>
                    
                    <p>Saludos,<br><strong>Equipo Imprenta Tucán</strong></p>
                </div>
                <div style="background: #f3f4f6; padding: 10px; text-align: center; font-size: 12px; color: #6b7280;">
                    <p>¿Querés dejar de recibir estos emails? <a href="{base_url}/api/tracking/unsubscribe/{token}/">Unsubscribe</a></p>
                </div>
                {pixel_tracking}
            </body>
            </html>
            """

            try:
                from core.notifications.engine import enviar_notificacion
                mensaje_texto = f"Hola {cliente.nombre},\n\n¡Te extrañamos! Han pasado {dias_sin_pedido} días desde tu último pedido.\n\nQueremos ofrecerte un descuento especial del 10% en tu próxima orden.\n\nVisita nuestro sitio para más información.\n\n¡Te esperamos de vuelta!\n\nSaludos,\nEquipo Imprenta Tucán"
                enviar_notificacion(
                    destinatario=cliente.email,
                    canal='email',
                    asunto='¡Te extrañamos! Descuento especial esperando por vos',
                    mensaje=mensaje_texto,
                    html=mensaje_html,
                    reply_to=reply_to,
                )
                
                EmailTracking.objects.create(
                    cliente=cliente,
                    tipo='cliente_inactivo',
                    token=token,
                    email_enviado=cliente.email,
                    asunto='¡Te extrañamos! Descuento especial esperando por vos',
                    estado='enviado',
                )
                
                AutomationLog.objects.create(
                    evento='cliente_inactivo_notificado',
                    descripcion=f'Notificación de reactivación enviada a {cliente.email}',
                    datos={'cliente_id': cliente.id, 'dias_sin_pedido': dias_sin_pedido, 'token': token},
                )
                enviados += 1
            except Exception as e:
                logger.warning(f'Error enviando notificación a cliente {cliente.id}: {e}')
                errores += 1

        except Exception as e:
            logger.warning(f'Error procesando cliente {cliente.id}: {e}')
            errores += 1

    return f'clientes_inactivos: {enviados} notificaciones enviadas, {errores} errores de {total} clientes inactivos'
