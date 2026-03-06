"""
Activación de campañas de fidelización por ascenso de tier.

Un "ascenso de tier" ocurre cuando el score de un cliente en el período actual
supera el umbral del siguiente nivel respecto al período anterior:
    Nuevo (< 30) → Estándar (30–60) → Estratégico (60–90) → Premium (≥ 90)

Al detectar el ascenso se:
    1. Crea una OfertaPropuesta de tipo 'fidelizacion' con mensaje personalizado.
    2. Envía notificación al cliente (email + portal) felicitando el avance.
    3. Registra el evento en AutomationLog.

Puede invocarse:
    a) Desde la tarea Celery `tarea_ranking_clientes` tras cada ciclo de ranking.
    b) Como comando standalone: detectar_y_activar_campanas_tier().

"""
import logging

logger = logging.getLogger(__name__)

# Tabla de tiers (igual que en ofertas.py para consistencia)
TIERS = [
    ('Premium',     90,  15),   # (nombre, score_min, descuento%)
    ('Estratégico', 60,  10),
    ('Estándar',    30,   7),
    ('Nuevo',        0,   5),
]


def _tier_para_score(score: float) -> str:
    for nombre, min_score, _ in TIERS:
        if score >= min_score:
            return nombre
    return 'Nuevo'


def _descuento_para_score(score: float) -> int:
    for _, min_score, descuento in TIERS:
        if score >= min_score:
            return descuento
    return 5


# ── Punto de entrada principal ────────────────────────────────────────────────

def detectar_y_activar_campanas_tier() -> dict:
    """
    Compara el score del período actual vs. el anterior para cada cliente.
    Si el tier subió, activa la campaña de bienvenida al nuevo nivel.

    Retorna:
        {'campanas_activadas': int, 'periodo': str}
    """
    try:
        from automatizacion.models import RankingHistorico
        from django.utils import timezone
    except ImportError as e:
        logger.error('campanas: error de importación — %s', e)
        return {'campanas_activadas': 0, 'error': str(e)}

    hoy = timezone.now()
    periodo_actual = hoy.strftime('%Y-%m')
    # período anterior: calcular manualmente para evitar dependencias
    if hoy.month == 1:
        periodo_anterior = f'{hoy.year - 1}-12'
    else:
        periodo_anterior = f'{hoy.year}-{hoy.month - 1:02d}'

    # Scores actuales y anteriores en una sola query
    actuales = {
        r['cliente_id']: r['score']
        for r in RankingHistorico.objects
        .filter(periodo=periodo_actual)
        .values('cliente_id', 'score')
    }
    anteriores = {
        r['cliente_id']: r['score']
        for r in RankingHistorico.objects
        .filter(periodo=periodo_anterior)
        .values('cliente_id', 'score')
    }

    activadas = 0
    for cliente_id, score_actual in actuales.items():
        score_prev = anteriores.get(cliente_id)
        if score_prev is None:
            continue  # cliente nuevo sin histórico anterior

        tier_actual = _tier_para_score(score_actual)
        tier_prev   = _tier_para_score(float(score_prev))

        if tier_actual == tier_prev:
            continue  # sin cambio de tier

        # Determinar si subió (tiers ordenados de mayor a menor en TIERS)
        orden = {nombre: i for i, (nombre, _, _) in enumerate(TIERS)}
        if orden.get(tier_actual, 99) < orden.get(tier_prev, 99):
            # Índice menor → tier más alto → ascendió
            _activar_campana_ascenso(
                cliente_id=cliente_id,
                tier_nuevo=tier_actual,
                tier_anterior=tier_prev,
                score_actual=score_actual,
                periodo=periodo_actual,
            )
            activadas += 1

    logger.info('campanas_tier: %d campañas activadas en período %s', activadas, periodo_actual)
    return {'campanas_activadas': activadas, 'periodo': periodo_actual}


def _activar_campana_ascenso(
    cliente_id: int,
    tier_nuevo: str,
    tier_anterior: str,
    score_actual: float,
    periodo: str,
) -> None:
    """Crea la OfertaPropuesta de fidelización y envía notificaciones."""
    try:
        from clientes.models import Cliente
        from automatizacion.models import OfertaPropuesta, AutomationLog
    except ImportError as e:
        logger.error('_activar_campana_ascenso: error de importación — %s', e)
        return

    try:
        cliente = Cliente.objects.get(id=cliente_id)
    except Exception:
        logger.warning('_activar_campana_ascenso: cliente_id=%s no encontrado', cliente_id)
        return

    # Evitar crear campaña duplicada en el mismo período
    ya_existe = OfertaPropuesta.objects.filter(
        cliente_id=cliente_id,
        tipo='fidelizacion',
        periodo=periodo,
        parametros__campana_tier=True,
    ).exists()
    if ya_existe:
        return

    descuento = _descuento_para_score(score_actual)
    titulo = f'¡Bienvenido al nivel {tier_nuevo}!'
    descripcion = (
        f'Estimado/a {cliente.nombre_completo if hasattr(cliente, "nombre_completo") else str(cliente)}, '
        f'su nivel de cliente ha ascendido de {tier_anterior} a {tier_nuevo}. '
        f'Como reconocimiento, le ofrecemos un {descuento}% de descuento en su próxima orden.'
    )

    oferta = OfertaPropuesta.objects.create(
        cliente_id=cliente_id,
        titulo=titulo,
        descripcion=descripcion,
        tipo='fidelizacion',
        estado='pendiente',
        periodo=periodo,
        score_al_generar=score_actual,
        parametros={
            'descuento': descuento,
            'tier_nuevo': tier_nuevo,
            'tier_anterior': tier_anterior,
            'campana_tier': True,
        },
    )

    # Notificación email
    try:
        from core.notifications.engine import enviar_notificacion
        if cliente.email:
            html = (
                f'<h2>{titulo}</h2>'
                f'<p>{descripcion}</p>'
                f'<p><strong>Su nuevo descuento: {descuento}%</strong></p>'
            )
            enviar_notificacion(
                destinatario=cliente.email,
                mensaje=descripcion,
                canal='email',
                asunto=titulo,
                html=html,
                metadata={'oferta_id': oferta.id, 'tier_nuevo': tier_nuevo},
            )
    except Exception as e:
        logger.warning('_activar_campana_ascenso: email falló — %s', e)

    # Notificación portal (siempre)
    try:
        from core.notifications.engine import enviar_notificacion
        enviar_notificacion(
            destinatario=str(cliente_id),
            mensaje=descripcion,
            canal='portal',
            asunto=titulo,
            metadata={'oferta_id': oferta.id, 'tier_nuevo': tier_nuevo, 'tipo': 'campana_tier'},
        )
    except Exception as e:
        logger.warning('_activar_campana_ascenso: portal log falló — %s', e)

    logger.info(
        'Campaña activada: cliente_id=%s  %s → %s  (oferta_id=%s)',
        cliente_id, tier_anterior, tier_nuevo, oferta.id,
    )


# ── Activar campaña por ID (compatible con firma original) ───────────────────

def activar_campana(campana_id: int) -> dict | None:
    """
    Activa (estado='enviada') una OfertaPropuesta específica por su PK
    y envía las notificaciones correspondientes.

    Compatible con la firma original del stub.
    """
    try:
        from automatizacion.models import OfertaPropuesta
    except ImportError as e:
        logger.error('activar_campana: error de importación — %s', e)
        return None

    try:
        oferta = OfertaPropuesta.objects.select_related('cliente').get(id=campana_id)
    except OfertaPropuesta.DoesNotExist:
        logger.warning('activar_campana: OfertaPropuesta id=%s no existe', campana_id)
        return None

    if oferta.estado not in ('pendiente',):
        logger.info('activar_campana: oferta id=%s ya en estado %s, omitiendo', campana_id, oferta.estado)
        return {'estado': oferta.estado, 'omitida': True}

    cliente = oferta.cliente
    descuento = oferta.parametros.get('descuento', 0)

    try:
        from core.notifications.engine import enviar_notificacion
        if cliente.email:
            html = f'<h2>{oferta.titulo}</h2><p>{oferta.descripcion}</p>'
            if descuento:
                html += f'<p><strong>Descuento: {descuento}%</strong></p>'
            enviar_notificacion(
                destinatario=cliente.email,
                mensaje=oferta.descripcion,
                canal='email',
                asunto=oferta.titulo,
                html=html,
                metadata={'oferta_id': oferta.id},
            )
        enviar_notificacion(
            destinatario=str(cliente.id),
            mensaje=oferta.descripcion,
            canal='portal',
            metadata={'oferta_id': oferta.id},
        )
    except Exception as e:
        logger.warning('activar_campana(id=%s): error en notificaciones — %s', campana_id, e)

    oferta.estado = 'enviada'
    from django.utils import timezone
    oferta.fecha_validacion = timezone.now()
    oferta.save(update_fields=['estado', 'fecha_validacion', 'actualizada'])

    return {'id': campana_id, 'estado': 'enviada', 'cliente': str(cliente)}

