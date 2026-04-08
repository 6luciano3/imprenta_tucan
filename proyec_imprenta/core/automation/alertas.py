"""
Alertas de retraso en pedidos.

Envía notificaciones internas y por email a los usuarios staff cuando
un pedido supera el tiempo de entrega esperado sin ser completado.
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def alerta_retraso(pedido_id: int) -> dict:
    """
    Verifica si el pedido está retrasado y emite alertas si corresponde.

    Un pedido se considera retrasado cuando:
        - Su estado no está en {'completado', 'cancelado', 'entregado'}
        - Han pasado más de N días desde su creación (N configurable, default 7).

    Returns:
        dict con 'retrasado': bool, 'dias_retraso': int, 'alertas_enviadas': int
    """
    try:
        from pedidos.models import Pedido
        from configuracion.models import Parametro

        pedido = Pedido.objects.select_related('cliente').get(pk=pedido_id)
    except Exception as exc:
        logger.warning('alerta_retraso: pedido %s no encontrado — %s', pedido_id, exc)
        return {'retrasado': False, 'dias_retraso': 0, 'alertas_enviadas': 0, 'error': str(exc)}

    try:
        from configuracion.models import Parametro
        umbral_dias = int(Parametro.get('ALERTA_RETRASO_DIAS', 7))
    except Exception:
        umbral_dias = 7

    estados_finales = {'completado', 'cancelado', 'entregado'}
    estado_actual = (getattr(pedido.estado, 'nombre', None) or str(getattr(pedido, 'estado', ''))).lower()

    if estado_actual in estados_finales:
        return {'retrasado': False, 'dias_retraso': 0, 'alertas_enviadas': 0}

    fecha_ref = getattr(pedido, 'fecha_pedido', None) or getattr(pedido, 'created_at', None)
    if not fecha_ref:
        return {'retrasado': False, 'dias_retraso': 0, 'alertas_enviadas': 0}

    dias_transcurridos = (timezone.now() - fecha_ref).days
    if dias_transcurridos <= umbral_dias:
        return {'retrasado': False, 'dias_retraso': 0, 'alertas_enviadas': 0}

    dias_retraso = dias_transcurridos - umbral_dias
    alertas = 0

    # Notificación interna a usuarios staff
    try:
        from usuarios.models import Usuario, Notificacion
        cliente_info = ''
        try:
            cliente_info = f' — Cliente: {pedido.cliente.nombre}'
        except Exception:
            pass

        mensaje = (
            f'⏰ Pedido #{pedido_id} retrasado {dias_retraso} día(s){cliente_info}. '
            f'Estado: {estado_actual}. Fecha creación: {fecha_ref.strftime("%d/%m/%Y")}.'
        )
        staff_ids = list(Usuario.objects.filter(is_staff=True, estado='Activo').values_list('id', flat=True))
        Notificacion.objects.bulk_create(
            [Notificacion(usuario_id=uid, mensaje=mensaje) for uid in staff_ids],
            ignore_conflicts=True,
        )
        alertas += len(staff_ids)
    except Exception as exc:
        logger.error('alerta_retraso: fallo notificación interna — %s', exc)

    # Registro en AutomationLog
    try:
        from automatizacion.models import AutomationLog
        AutomationLog.objects.create(
            evento='alerta_retraso',
            descripcion=f'Pedido #{pedido_id} retrasado {dias_retraso} días',
            datos={'pedido_id': pedido_id, 'dias_retraso': dias_retraso, 'estado': estado_actual},
        )
    except Exception:
        pass

    logger.info('alerta_retraso: pedido %s retrasado %s días, %s alertas enviadas.', pedido_id, dias_retraso, alertas)
    return {'retrasado': True, 'dias_retraso': dias_retraso, 'alertas_enviadas': alertas}


def revisar_pedidos_retrasados() -> dict:
    """
    Revisa todos los pedidos activos y emite alertas para los retrasados.
    Llamada por la tarea Celery `tarea_alertas_retraso`.

    Returns:
        {'revisados': int, 'retrasados': int, 'alertas_enviadas': int}
    """
    try:
        from pedidos.models import Pedido
    except Exception as exc:
        return {'revisados': 0, 'retrasados': 0, 'alertas_enviadas': 0, 'error': str(exc)}

    estados_finales = {'completado', 'cancelado', 'entregado'}
    try:
        pedidos = Pedido.objects.exclude(estado__nombre__in=estados_finales).select_related('estado', 'cliente')
    except Exception:
        pedidos = Pedido.objects.all().select_related('estado', 'cliente')

    revisados = retrasados = alertas_totales = 0
    for pedido in pedidos:
        resultado = alerta_retraso(pedido.pk)
        revisados += 1
        if resultado.get('retrasado'):
            retrasados += 1
            alertas_totales += resultado.get('alertas_enviadas', 0)

    return {'revisados': revisados, 'retrasados': retrasados, 'alertas_enviadas': alertas_totales}

