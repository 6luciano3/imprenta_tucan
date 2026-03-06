"""
Motor de notificaciones multicanal.

Canales soportados:
    email     → Django send_mail (ya configurado en settings)
    sms       → Twilio REST API  (requiere TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER en BD)
    whatsapp  → HTTP POST a URL configurable (WHATSAPP_API_URL + WHATSAPP_API_TOKEN en BD)
    portal    → Registro en AutomationLog visible en el panel interno

Uso:
    from core.notifications.engine import enviar_notificacion

    result = enviar_notificacion(
        destinatario='cliente@email.com',   # email, teléfono o user_id según canal
        mensaje='Su pedido fue aprobado.',
        canal='email',
        asunto='Notificación de pedido',    # solo para email
        html='<b>Su pedido fue aprobado.</b>',  # opcional email
        metadata={'pedido_id': 42},         # opcional, guardado en log
    )
    # result = {'ok': True} | {'ok': False, 'error': '...'}
"""
import logging

logger = logging.getLogger(__name__)


def enviar_notificacion(
    destinatario: str,
    mensaje: str,
    canal: str = 'email',
    asunto: str | None = None,
    html: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """
    Despacha una notificación al canal indicado.

    Args:
        destinatario: Dirección email, número de teléfono (+5491...) o identificador interno.
        mensaje:      Cuerpo en texto plano.
        canal:        'email' | 'sms' | 'whatsapp' | 'portal'
        asunto:       Asunto (solo email).
        html:         Cuerpo HTML alternativo (solo email).
        metadata:     Datos adicionales registrados en el log interno.

    Returns:
        {'ok': True} si la notificación fue enviada correctamente.
        {'ok': False, 'error': str} en caso de fallo.
    """
    canal = (canal or 'email').lower().strip()
    metadata = metadata or {}

    dispatchers = {
        'email':    _enviar_email,
        'sms':      _enviar_sms,
        'whatsapp': _enviar_whatsapp,
        'portal':   _enviar_portal,
    }

    handler = dispatchers.get(canal)
    if handler is None:
        err = f'Canal desconocido: {canal!r}. Canales válidos: {list(dispatchers)}'
        logger.warning('enviar_notificacion: %s', err)
        return {'ok': False, 'error': err}

    try:
        resultado = handler(destinatario, mensaje, asunto=asunto, html=html, metadata=metadata)
        _registrar_log(destinatario, canal, mensaje, metadata, exito=resultado.get('ok', False))
        return resultado
    except Exception as exc:
        logger.exception('enviar_notificacion(%s): excepción inesperada', canal)
        _registrar_log(destinatario, canal, mensaje, metadata, exito=False, error=str(exc))
        return {'ok': False, 'error': str(exc)}


# ── Canal: email ─────────────────────────────────────────────────────────────

def _enviar_email(destinatario, mensaje, *, asunto=None, html=None, metadata=None):
    from django.core.mail import send_mail, EmailMultiAlternatives
    from django.conf import settings

    remitente = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@imprentatucan.com')
    asunto = asunto or 'Notificación — Imprenta Tucán'

    if html:
        msg = EmailMultiAlternatives(asunto, mensaje, remitente, [destinatario])
        msg.attach_alternative(html, 'text/html')
        msg.send()
    else:
        send_mail(asunto, mensaje, remitente, [destinatario], fail_silently=False)

    logger.info('email enviado a %s: %s', destinatario, asunto)
    return {'ok': True}


# ── Canal: SMS (Twilio) ───────────────────────────────────────────────────────

def _enviar_sms(destinatario, mensaje, *, asunto=None, html=None, metadata=None):
    """
    Envía SMS vía Twilio si las credenciales están configuradas en BD (Parametro).
    Si no están configuradas, registra advertencia y retorna error gracioso.
    """
    try:
        from configuracion.models import Parametro
        account_sid = Parametro.get('TWILIO_ACCOUNT_SID', '')
        auth_token  = Parametro.get('TWILIO_AUTH_TOKEN', '')
        from_number = Parametro.get('TWILIO_FROM_NUMBER', '')
    except Exception as e:
        return {'ok': False, 'error': f'No se pudo leer la config de Twilio: {e}'}

    if not account_sid or not auth_token or not from_number:
        logger.warning(
            'SMS no enviado a %s: credenciales Twilio no configuradas '
            '(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER en Parametro).',
            destinatario,
        )
        return {
            'ok': False,
            'error': 'Credenciales Twilio no configuradas. Configura TWILIO_ACCOUNT_SID, '
                     'TWILIO_AUTH_TOKEN y TWILIO_FROM_NUMBER en Configuración > Parámetros.',
        }

    try:
        import requests
        url = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'
        response = requests.post(
            url,
            data={'From': from_number, 'To': destinatario, 'Body': mensaje},
            auth=(account_sid, auth_token),
            timeout=15,
        )
        response.raise_for_status()
        sid = response.json().get('sid', '')
        logger.info('SMS enviado a %s (SID: %s)', destinatario, sid)
        return {'ok': True, 'sid': sid}
    except Exception as exc:
        logger.error('SMS Twilio falló para %s: %s', destinatario, exc)
        return {'ok': False, 'error': str(exc)}


# ── Canal: WhatsApp (API configurable) ───────────────────────────────────────

def _enviar_whatsapp(destinatario, mensaje, *, asunto=None, html=None, metadata=None):
    """
    Envía mensaje WhatsApp vía API HTTP configurable.
    Compatible con providers como:
      - Twilio WhatsApp (agrega prefijo 'whatsapp:' automáticamente)
      - 360dialog, MessageBird, Meta Cloud API, etc.

    Parámetros requeridos en BD (Parametro):
        WHATSAPP_API_URL   → endpoint HTTP al que se hace POST
        WHATSAPP_API_TOKEN → bearer token o API key
    """
    try:
        from configuracion.models import Parametro
        api_url   = Parametro.get('WHATSAPP_API_URL', '')
        api_token = Parametro.get('WHATSAPP_API_TOKEN', '')
    except Exception as e:
        return {'ok': False, 'error': f'No se pudo leer la config de WhatsApp: {e}'}

    if not api_url:
        logger.warning(
            'WhatsApp no enviado a %s: WHATSAPP_API_URL no configurada.',
            destinatario,
        )
        return {
            'ok': False,
            'error': 'WHATSAPP_API_URL no configurada. '
                     'Configura WHATSAPP_API_URL y WHATSAPP_API_TOKEN en Configuración > Parámetros.',
        }

    try:
        import requests
        headers = {'Content-Type': 'application/json'}
        if api_token:
            headers['Authorization'] = f'Bearer {api_token}'

        payload = {
            'to':      destinatario,
            'message': mensaje,
            'type':    'text',
        }
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        logger.info('WhatsApp enviado a %s', destinatario)
        return {'ok': True}
    except Exception as exc:
        logger.error('WhatsApp API falló para %s: %s', destinatario, exc)
        return {'ok': False, 'error': str(exc)}


# ── Canal: Portal (notificación interna) ─────────────────────────────────────

def _enviar_portal(destinatario, mensaje, *, asunto=None, html=None, metadata=None):
    """
    Registra la notificación en AutomationLog (visible en el panel interno).
    'destinatario' puede ser un user_id, username o cualquier identificador.
    """
    try:
        from automatizacion.models import AutomationLog
        AutomationLog.objects.create(
            evento='notificacion_portal',
            descripcion=f'[{asunto or "sin asunto"}] {mensaje[:200]}',
            datos={
                'destinatario': destinatario,
                'asunto': asunto or '',
                'mensaje': mensaje,
                **(metadata or {}),
            },
        )
        logger.info('Notificación portal registrada para %s', destinatario)
        return {'ok': True}
    except Exception as exc:
        logger.error('Portal log falló: %s', exc)
        return {'ok': False, 'error': str(exc)}


# ── Log interno ───────────────────────────────────────────────────────────────

def _registrar_log(destinatario, canal, mensaje, metadata, *, exito, error=''):
    try:
        from automatizacion.models import AutomationLog
        AutomationLog.objects.create(
            evento=f'notificacion_{canal}',
            descripcion=f'Canal={canal} dest={destinatario} ok={exito}' + (f' err={error}' if error else ''),
            datos={
                'destinatario': destinatario,
                'ok': exito,
                'error': error,
                'mensaje_preview': mensaje[:120],
                **(metadata or {}),
            },
        )
    except Exception:
        pass  # El log es best-effort; nunca debe romper el flujo principal

