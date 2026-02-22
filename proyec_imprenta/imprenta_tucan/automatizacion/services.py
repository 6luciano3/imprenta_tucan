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
    link_ver = f"{url_base}/automatizacion/oferta/{token}/"
    # Tracking pixel
    tracking_pixel = f'<img src="{url_base}/automatizacion/acciones/callback/?cliente_id={cliente_id}&oferta_id={oferta_id}&tipo=leido&canal=email" width="1" height="1" style="display:none;" alt="" />'
    # Email HTML personalizado para Combo Emprendedor (coincidencia flexible)
    titulo_normalizado = oferta.titulo.strip().lower()
    if 'combo' in titulo_normalizado and 'emprendedor' in titulo_normalizado:
        html_body = f'''
        <div style="margin-bottom: 24px;">
            <h2 style="color:#1976d2;font-size:2.2rem;font-weight:800;margin-bottom:8px;">Combos con Descuento <span style="font-size:1.2rem;color:#388e3c;">– Imprenta Tucán</span></h2>
            <p style="color:#37474f;font-size:12px;">Hola {oferta.cliente.nombre or oferta.cliente.razon_social or ''},<br>
            En Imprenta Tucán lanzamos combos especiales con descuentos de hasta el <strong style="color:#d32f2f;">10%</strong>.</p>
        </div>
        <div style="background:#f9fafc;border-radius:16px;box-shadow:0 2px 8px rgba(0,0,0,0.07);padding:32px 24px;">
            <div style="color:#1a237e;font-size:2rem;font-weight:700;margin-bottom:8px;letter-spacing:0.5px;">Combo Emprendedor</div>
            <div style="color:#37474f;font-size:12px;margin-bottom:18px;">Oferta especial para emprendedores: productos impresos y servicios esenciales.</div>
            <table style="width:100%;border-collapse:collapse;margin-bottom:18px;font-size:12px;">
                <thead>
                    <tr style="background:#e3f2fd;color:#1976d2;font-weight:600;">
                        <th style="padding:10px 8px;border-bottom:2px solid #90caf9;">Producto</th>
                        <th style="padding:10px 8px;border-bottom:2px solid #90caf9;">Cantidad</th>
                        <th style="padding:10px 8px;border-bottom:2px solid #90caf9;">Precio Unitario</th>
                        <th style="padding:10px 8px;border-bottom:2px solid #90caf9;">Subtotal</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td style="padding:8px 6px;text-align:left;">Tarjetas personales full color</td><td style="padding:8px 6px;">500</td><td style="padding:8px 6px;">$45</td><td style="padding:8px 6px;">$22.500</td></tr>
                    <tr><td style="padding:8px 6px;text-align:left;">Volantes A5 color frente</td><td style="padding:8px 6px;">1000</td><td style="padding:8px 6px;">$35</td><td style="padding:8px 6px;">$35.000</td></tr>
                    <tr><td style="padding:8px 6px;text-align:left;">Banner 80x200 con estructura</td><td style="padding:8px 6px;">1</td><td style="padding:8px 6px;">$95.000</td><td style="padding:8px 6px;">$95.000</td></tr>
                    <tr><td style="padding:8px 6px;text-align:left;">Sello automático</td><td style="padding:8px 6px;">1</td><td style="padding:8px 6px;">$28.000</td><td style="padding:8px 6px;">$28.000</td></tr>
                </tbody>
            </table>
            <div style="font-size:12px;color:#263238;margin-bottom:4px;text-align:right;"><strong>Subtotal:</strong> $180.500</div>
            <div style="font-size:12px;color:#d32f2f;font-weight:600;text-align:right;"><strong>Descuento Combo (10%):</strong> -$18.050</div>
            <div style="font-size:12px;color:#388e3c;font-weight:700;margin-top:8px;text-align:right;"><strong>Total Final:</strong> $162.450</div>
        </div>
        <p style="margin-top:24px;">
            <a href="{link_aceptar}" style="background:#22c55e;color:white;padding:8px 16px;border-radius:6px;text-decoration:none;">Aceptar oferta</a>
            &nbsp;
            <a href="{link_rechazar}" style="background:#ef4444;color:white;padding:8px 16px;border-radius:6px;text-decoration:none;">Rechazar oferta</a>
        </p>
        <p>
            <a href="{link_ver}">Ver todas mis ofertas</a>
        </p>
        {tracking_pixel}
        '''
    else:
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
