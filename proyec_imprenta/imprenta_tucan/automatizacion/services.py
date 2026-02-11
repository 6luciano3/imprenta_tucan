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
    # Link a la página de ofertas del cliente si se dispone de request
    url = ''
    try:
        if request is not None:
            url = request.build_absolute_uri(reverse('mis_ofertas_cliente'))
    except Exception:
        url = ''
    body_lines = [
        f"Hola {oferta.cliente.nombre or oferta.cliente.razon_social or ''},",
        "Tenemos una oferta para vos:",
        f"Título: {oferta.titulo}",
        f"Descripción: {oferta.descripcion}",
    ]
    if url:
        body_lines.append("")
        body_lines.append(f"Podés verla y aceptarla acá: {url}")
    body = "\n".join(body_lines)
    try:
        send_mail(
            subject,
            body,
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@imprenta.local'),
            [oferta.cliente.email],
            fail_silently=False,
        )
        return True, None
    except Exception as e:
        return False, str(e)
