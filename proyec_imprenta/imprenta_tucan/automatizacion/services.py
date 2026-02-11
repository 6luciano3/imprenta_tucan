from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse


def enviar_oferta_email(oferta, request=None):
    """Envía por email el detalle de la oferta al cliente.
    Retorna (ok: bool, error: str | None).
    """
    if not oferta.cliente or not oferta.cliente.email:
        return False, 'Cliente sin email definido'
    subject = f"Nueva oferta: {oferta.titulo}"
    # Construir links de acción y tracking pixel
    url_base = ''
    if request is not None:
        url_base = request.build_absolute_uri('/')[:-1]  # quitar barra final
    oferta_id = oferta.id
    cliente_id = oferta.cliente.id
    # Links de acción con token único
    token = oferta.token_email or ''
    link_aceptar = f"{url_base}/automatizacion/oferta/{token}/aceptar/"
    link_rechazar = f"{url_base}/automatizacion/oferta/{token}/rechazar/"
    link_ver = f"{url_base}/automatizacion/mis-ofertas/"
    # Tracking pixel
    tracking_pixel = f'<img src="{url_base}/automatizacion/acciones/callback/?cliente_id={cliente_id}&oferta_id={oferta_id}&tipo=leido&canal=email" width="1" height="1" style="display:none;" alt="" />'
    # Email HTML
    html_body = f'''
    <p>Hola {oferta.cliente.nombre or oferta.cliente.razon_social or ''},</p>
    <p>Tenemos una oferta para vos:</p>
    <ul>
        <li><b>Título:</b> {oferta.titulo}</li>
        <li><b>Descripción:</b> {oferta.descripcion}</li>
    </ul>
    <p>
        <a href="{link_aceptar}" style="background:#22c55e;color:white;padding:8px 16px;border-radius:6px;text-decoration:none;">Aceptar oferta</a>
        &nbsp;
        <a href="{link_rechazar}" style="background:#ef4444;color:white;padding:8px 16px;border-radius:6px;text-decoration:none;">Rechazar oferta</a>
    </p>
    <p>
        <a href="{link_ver}">Ver todas mis ofertas</a>
    </p>
    {tracking_pixel}
    '''
    try:
        send_mail(
            subject,
            '',  # plain text vacío
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@imprenta.local'),
            [oferta.cliente.email],
            fail_silently=False,
            html_message=html_body
        )
        return True, None
    except Exception as e:
        return False, str(e)
