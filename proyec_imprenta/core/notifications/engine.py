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
    attachments: list | None = None,
    reply_to: str | None = None,
    media_url: str | None = None,
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
        reply_to:     Email de respuesta (solo email).
        media_url:    URL de imagen para WhatsApp.

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
        # WhatsApp no usa reply_to
        if canal == 'whatsapp':
            resultado = handler(destinatario, mensaje, asunto=asunto, html=html, metadata=metadata, attachments=attachments, media_url=media_url)
        else:
            resultado = handler(destinatario, mensaje, asunto=asunto, html=html, metadata=metadata, attachments=attachments, reply_to=reply_to)
        _registrar_log(destinatario, canal, mensaje, metadata, exito=resultado.get('ok', False))
        return resultado
    except Exception as exc:
        logger.exception('enviar_notificacion(%s): excepción inesperada', canal)
        _registrar_log(destinatario, canal, mensaje, metadata, exito=False, error=str(exc))
        return {'ok': False, 'error': str(exc)}


# ── Canal: email ─────────────────────────────────────────────────────────────

def _enviar_email(destinatario, mensaje, *, asunto=None, html=None, metadata=None, attachments=None, reply_to=None):
    from django.core.mail import send_mail, EmailMultiAlternatives
    from django.conf import settings

    remitente = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@imprentatucan.com')
    asunto = asunto or 'Notificación — Imprenta Tucán'

    if html or attachments:
        msg = EmailMultiAlternatives(asunto, mensaje, remitente, [destinatario])
        if html:
            msg.attach_alternative(html, 'text/html')
        for att in (attachments or []):
            msg.attach(*att)
        if reply_to:
            msg.reply_to = [reply_to]
        msg.send()
    else:
        send_mail(asunto, mensaje, remitente, [destinatario], fail_silently=False, reply_to=[reply_to] if reply_to else None)

    logger.info('email enviado a %s: %s', destinatario, asunto)
    return {'ok': True}


# ── Canal: SMS (Twilio) ───────────────────────────────────────────────────────

_E164_RE = None  # compilado la primera vez que se necesita


def _validar_e164(numero: str) -> bool:
    """Valida que el número esté en formato E.164: +<código de país><número>, 8–15 dígitos."""
    import re
    global _E164_RE
    if _E164_RE is None:
        _E164_RE = re.compile(r'^\+[1-9]\d{7,14}$')
    return bool(_E164_RE.match(numero))


def _normalizar_numero_e164(numero: str) -> str:
    """Convierte un número argentino al formato E.164."""
    import re
    # Limpiar el número de caracteres no numéricos
    digits = re.sub(r'\D', '', numero)
    
    # Si ya tiene prefijo internacional (54 o 549), agregar +
    if digits.startswith('549'):
        return '+' + digits
    elif digits.startswith('54'):
        return '+' + digits
    elif digits.startswith('9') and len(digits) == 10:
        # 9 followed by 10 digits for Argentina
        return '+54' + digits
    elif len(digits) == 10:
        # Asumir número argentino sin prefijo
        return '+54' + digits
    elif digits.startswith('+'):
        return digits
    else:
        # Devolver como está si no se puede determinar
        return '+' + digits


def _enviar_sms(destinatario, mensaje, *, asunto=None, html=None, metadata=None, attachments=None):
    """
    Envía SMS vía SDK oficial de Twilio.

    Requiere en BD (Configuración > Parámetros):
        TWILIO_ACCOUNT_SID  — Account SID de la consola Twilio
        TWILIO_AUTH_TOKEN   — Auth Token de la consola Twilio
        TWILIO_FROM_NUMBER  — Número remitente en formato E.164 (+1415XXXXXXX)

    El número destinatario también debe estar en formato E.164.
    """
    # ── 1. Validar formato del destinatario ───────────────────────────────────
    if not _validar_e164(destinatario):
        err = (
            f'Número de teléfono inválido: {destinatario!r}. '
            'Debe estar en formato E.164 (ej: +5493816123456).'
        )
        logger.warning('SMS rechazado: %s', err)
        return {'ok': False, 'error': err}

    # ── 2. Leer credenciales: BD primero, variables de entorno como fallback ──
    try:
        from configuracion.models import Parametro
        account_sid = Parametro.get('TWILIO_ACCOUNT_SID', '')
        auth_token  = Parametro.get('TWILIO_AUTH_TOKEN', '')
        from_number = Parametro.get('TWILIO_FROM_NUMBER', '')
    except Exception as e:
        logger.warning('SMS: no se pudo leer config de BD (%s), usando variables de entorno.', e)
        account_sid = auth_token = from_number = ''

    # Variables de entorno como fallback (útil en CI, Docker, entornos sin BD lista)
    import os
    account_sid = account_sid or os.environ.get('TWILIO_ACCOUNT_SID', '')
    auth_token  = auth_token  or os.environ.get('TWILIO_AUTH_TOKEN', '')
    from_number = from_number or os.environ.get('TWILIO_FROM_NUMBER', '')

    if not account_sid or not auth_token or not from_number:
        # ── Modo desarrollo: simular el envío sin fallar ───────────────────────
        from django.conf import settings
        if getattr(settings, 'DEBUG', False):
            logger.warning(
                '[SMS SIMULADO] Credenciales Twilio no configuradas. '
                'Destinatario: %s | Mensaje: %.80s',
                destinatario, mensaje,
            )
            return {
                'ok': True,
                'simulated': True,
                'warning': 'SMS simulado — credenciales Twilio no configuradas (DEBUG=True).',
            }
        # Producción: informar claramente sin lanzar excepción
        logger.warning(
            'SMS no enviado a %s: credenciales Twilio ausentes '
            '(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER).',
            destinatario,
        )
        return {
            'ok': False,
            'error': (
                'Credenciales Twilio no configuradas. '
                'Agrega TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN y TWILIO_FROM_NUMBER '
                'en Configuración > Parámetros o como variables de entorno.'
            ),
        }

    if not _validar_e164(from_number):
        logger.error('SMS: TWILIO_FROM_NUMBER no está en formato E.164: %s', from_number)
        return {
            'ok': False,
            'error': f'TWILIO_FROM_NUMBER tiene formato inválido: {from_number!r}. Usa E.164.',
        }

    # ── 3. Enviar con el SDK oficial de Twilio ────────────────────────────────
    try:
        from twilio.rest import Client
        from twilio.base.exceptions import TwilioRestException

        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=mensaje,
            from_=from_number,
            to=destinatario,
        )
        logger.info(
            'SMS enviado a %s — SID: %s, estado: %s',
            destinatario, message.sid, message.status,
        )
        return {'ok': True, 'sid': message.sid, 'status': message.status}

    except TwilioRestException as exc:
        # Errores de autenticación (20003), número inválido (21211), etc.
        logger.error(
            'SMS Twilio error %s a %s: %s',
            exc.code, destinatario, exc.msg,
        )
        return {
            'ok': False,
            'error': f'Twilio error {exc.code}: {exc.msg}',
            'twilio_code': exc.code,
        }

    except ConnectionError as exc:
        logger.error('SMS: error de red al conectar con Twilio: %s', exc)
        return {'ok': False, 'error': f'Error de red: {exc}'}

    except Exception as exc:
        logger.exception('SMS: excepción inesperada para %s', destinatario)
        return {'ok': False, 'error': str(exc)}


# ── Canal: WhatsApp (Meta Cloud API / Twilio WhatsApp) ───────────────────────
#
# Proveedor seleccionado con el parámetro WHATSAPP_PROVIDER en BD:
#   'meta'   → Meta Cloud API (graph.facebook.com) — recomendado para producción
#   'twilio' → Twilio WhatsApp sandbox o número aprobado (usa el SDK ya instalado)
#
# Parámetros comunes (Configuración > Parámetros):
#   WHATSAPP_PROVIDER        'meta' | 'twilio'  (por defecto 'meta')
#   WHATSAPP_API_TOKEN       Bearer token (Meta) o Auth Token (Twilio)
#
# Parámetros exclusivos Meta:
#   WHATSAPP_PHONE_NUMBER_ID  Phone Number ID de la app Meta (no el número visible)
#
# Parámetros exclusivos Twilio:
#   TWILIO_ACCOUNT_SID        (se reutiliza del canal SMS)
#   TWILIO_WHATSAPP_FROM      número remitente con prefijo  whatsapp:+1415XXXXXXX


def _build_payload_meta(destinatario: str, mensaje: str) -> dict:
    """Payload para Meta Cloud API (messages endpoint v17+)."""
    return {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': destinatario,
        'type': 'text',
        'text': {'preview_url': False, 'body': mensaje},
    }


def _enviar_whatsapp_meta(destinatario: str, mensaje: str, phone_number_id: str, token: str) -> dict:
    import requests

    url = f'https://graph.facebook.com/v19.0/{phone_number_id}/messages'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    payload = _build_payload_meta(destinatario, mensaje)

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
    except ConnectionError as exc:
        logger.error('WhatsApp Meta: error de red: %s', exc)
        return {'ok': False, 'error': f'Error de red: {exc}'}

    if not resp.ok:
        # Meta devuelve detalles de error en JSON
        try:
            err_data = resp.json().get('error', {})
            err_msg = err_data.get('message', resp.text)
            err_code = err_data.get('code', resp.status_code)
        except Exception:
            err_msg, err_code = resp.text, resp.status_code
        logger.error('WhatsApp Meta HTTP %s a %s: %s', err_code, destinatario, err_msg)
        return {'ok': False, 'error': f'Meta API error {err_code}: {err_msg}'}

    try:
        msg_id = resp.json().get('messages', [{}])[0].get('id', '')
    except Exception:
        msg_id = ''

    logger.info('WhatsApp Meta enviado a %s — message_id: %s', destinatario, msg_id)
    return {'ok': True, 'message_id': msg_id}


def _enviar_whatsapp_twilio(destinatario: str, mensaje: str, account_sid: str, auth_token: str, from_number: str, attachments=None, media_url=None) -> dict:
    try:
        from twilio.rest import Client
        from twilio.base.exceptions import TwilioRestException
    except ImportError:
        return {'ok': False, 'error': 'SDK twilio no instalado. Ejecuta: pip install "twilio>=9.0,<10"'}

    # Twilio WhatsApp requiere el prefijo 'whatsapp:' en ambos extremos
    to_wa   = destinatario if destinatario.startswith('whatsapp:') else f'whatsapp:{destinatario}'
    from_wa = from_number  if from_number.startswith('whatsapp:')  else f'whatsapp:{from_number}'

    try:
        client  = Client(account_sid, auth_token)
        
        # Preparar parámetros del mensaje
        msg_params = {
            'body': mensaje,
            'from_': from_wa,
            'to': to_wa,
        }
        
        # Agregar URL de media si se proporciona
        if media_url:
            msg_params['media_url'] = [media_url]
            logger.info('WhatsApp Twilio: enviando con imagen desde %s', media_url)
        
        message = client.messages.create(**msg_params)
        logger.info('WhatsApp Twilio enviado a %s — SID: %s, estado: %s',
                    destinatario, message.sid, message.status)
        return {'ok': True, 'sid': message.sid, 'status': message.status}

    except TwilioRestException as exc:
        logger.error('WhatsApp Twilio error %s a %s: %s', exc.code, destinatario, exc.msg)
        return {'ok': False, 'error': f'Twilio error {exc.code}: {exc.msg}', 'twilio_code': exc.code}

    except ConnectionError as exc:
        logger.error('WhatsApp Twilio: error de red: %s', exc)
        return {'ok': False, 'error': f'Error de red: {exc}'}

    except Exception as exc:
        logger.exception('WhatsApp Twilio: excepción inesperada para %s', destinatario)
        return {'ok': False, 'error': str(exc)}


def _whatsapp_sin_credenciales(destinatario: str, mensaje: str, *, faltantes: str, proveedor: str) -> dict:
    """
    Maneja el caso de credenciales incompletas.
    Siempre retorna error (no simula) ya que necesitamos que funcione en producción.
    """
    logger.warning(
        'WhatsApp %s no enviado a %s: faltan %s.',
        proveedor, destinatario, faltantes,
    )
    return {
        'ok': False,
        'error': (
            f'WhatsApp {proveedor} no configurado. '
            f'Agrega {faltantes} en Configuración > Parámetros '
            'o como variables de entorno.'
        ),
    }


def _enviar_whatsapp(destinatario, mensaje, *, asunto=None, html=None, metadata=None, attachments=None, media_url=None):
    """
    Envía mensaje de WhatsApp Business.

    Proveedores soportados (WHATSAPP_PROVIDER en BD):
        'meta'   → Meta Cloud API  (por defecto)
        'twilio' → Twilio WhatsApp Business
    """
    # ── 1. Normalizar y validar formato del destinatario ─────────────────────
    numero_limpio = destinatario.removeprefix('whatsapp:')
    
    # Intentar normalizar si no está en formato E.164
    if not _validar_e164(numero_limpio):
        numero_limpio = _normalizar_numero_e164(numero_limpio)
    
    if not _validar_e164(numero_limpio):
        err = (
            f'Número de teléfono inválido: {destinatario!r}. '
            'Debe estar en formato E.164 (ej: +5493816123456).'
        )
        logger.warning('WhatsApp rechazado: %s', err)
        return {'ok': False, 'error': err}

    # ── 2. Leer configuración: BD primero, variables de entorno como fallback ─
    import os
    try:
        from configuracion.models import Parametro
        proveedor       = Parametro.get('WHATSAPP_PROVIDER', '')
        api_token       = Parametro.get('WHATSAPP_API_TOKEN', '')
        phone_number_id = Parametro.get('WHATSAPP_PHONE_NUMBER_ID', '')   # Meta
        account_sid     = Parametro.get('TWILIO_ACCOUNT_SID', '')         # Twilio
        auth_token      = Parametro.get('TWILIO_AUTH_TOKEN', '')          # Twilio
        from_number     = Parametro.get('TWILIO_WHATSAPP_FROM', '')       # Twilio
    except Exception as e:
        logger.warning('WhatsApp: no se pudo leer config de BD (%s), usando variables de entorno.', e)
        proveedor = api_token = phone_number_id = account_sid = auth_token = from_number = ''

    # Variables de entorno como fallback
    proveedor       = (proveedor       or os.environ.get('WHATSAPP_PROVIDER', 'twilio')).lower().strip()
    api_token       = api_token        or os.environ.get('WHATSAPP_API_TOKEN', '')
    phone_number_id = phone_number_id  or os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')
    account_sid     = account_sid      or os.environ.get('TWILIO_ACCOUNT_SID', '')
    auth_token      = auth_token       or os.environ.get('TWILIO_AUTH_TOKEN', '')
    from_number     = from_number      or os.environ.get('TWILIO_WHATSAPP_FROM', '')

    # ── 3. Delegar al proveedor seleccionado ─────────────────────────────────
    if proveedor == 'meta':
        if not api_token or not phone_number_id:
            return _whatsapp_sin_credenciales(
                destinatario, mensaje,
                faltantes='WHATSAPP_API_TOKEN y WHATSAPP_PHONE_NUMBER_ID',
                proveedor='Meta',
            )
        return _enviar_whatsapp_meta(numero_limpio, mensaje, phone_number_id, api_token)

    elif proveedor == 'twilio':
        if not account_sid or not auth_token or not from_number:
            return _whatsapp_sin_credenciales(
                destinatario, mensaje,
                faltantes='TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN y TWILIO_WHATSAPP_FROM',
                proveedor='Twilio',
            )
        return _enviar_whatsapp_twilio(numero_limpio, mensaje, account_sid, auth_token, from_number, media_url=media_url)

    else:
        err = f'Proveedor WhatsApp desconocido: {proveedor!r}. Valores válidos: "meta", "twilio".'
        logger.error('WhatsApp: %s', err)
        return {'ok': False, 'error': err}


# ── Canal: Portal (notificación interna) ─────────────────────────────────────

def _enviar_portal(destinatario, mensaje, *, asunto=None, html=None, metadata=None, attachments=None):
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

