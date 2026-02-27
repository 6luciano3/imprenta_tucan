# automatizacion/services.py
from django.core.mail import send_mail
from django.conf import settings

def _html_tabla_combo(combo):
    filas = ''
    for cop in combo.comboofertaproducto_set.select_related('producto').all():
        precio = float(cop.producto.precioUnitario or 0)
        cant = int(cop.cantidad or 1)
        sub = precio * cant
        filas += f'<tr><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;">{cop.producto.nombreProducto}</td><td style="padding:9px 12px;text-align:center;">{cant}</td><td style="padding:9px 12px;text-align:right;"></td><td style="padding:9px 12px;text-align:right;font-weight:600;"></td></tr>'
    subtotal = sum(float(c.producto.precioUnitario or 0)*int(c.cantidad or 1) for c in combo.comboofertaproducto_set.select_related('producto').all())
    descuento = float(combo.descuento or 0)
    descuento_valor = subtotal * descuento / 100
    return filas, subtotal, descuento, descuento_valor, subtotal - descuento_valor

def enviar_oferta_email(oferta, request=None):
    if not oferta.cliente or not oferta.cliente.email:
        return False, 'Cliente sin email definido'
    cliente = oferta.cliente
    url_base = request.build_absolute_uri('/')[:-1] if request else ''
    token = oferta.token_email or ''
    link_aceptar  = f'{url_base}/automatizacion/oferta/{token}/aceptar/'
    link_rechazar = f'{url_base}/automatizacion/oferta/{token}/rechazar/'
    link_ver      = f'{url_base}/automatizacion/oferta/{token}/'
    pixel = f'<img src="{url_base}/automatizacion/acciones/pixel/?cliente_id={cliente.id}&oferta_id={oferta.id}&tipo=leido&canal=email" width="1" height="1" style="display:none;" alt="" />'
    nombre = getattr(cliente,'nombre','') or getattr(cliente,'razon_social','') or 'Cliente'
    from automatizacion.views_combos import generar_combo_para_cliente
    combo = generar_combo_para_cliente(cliente)
    if combo and combo.comboofertaproducto_set.exists():
        filas, subtotal, descuento, desc_valor, total = _html_tabla_combo(combo)
        bloque = (f'<div style="background:#f9fafc;border-radius:12px;border:1px solid #e3eaf2;padding:24px;margin-bottom:24px;">'
                  f'<div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#1a237e;margin-bottom:6px;">{combo.nombre}</div>'
                  f'<div style="font-size:12px;color:#607d8b;margin-bottom:16px;">{combo.descripcion}</div>'
                  f'<table style="width:100%;border-collapse:collapse;font-size:12px;">'
                  f'<thead><tr style="background:#1565c0;color:#fff;"><th style="padding:10px 12px;text-align:left;">Producto</th><th style="padding:10px 12px;text-align:center;">Cant.</th><th style="padding:10px 12px;text-align:right;">P.Unit.</th><th style="padding:10px 12px;text-align:right;">Subtotal</th></tr></thead>'
                  f'<tbody>{filas}</tbody></table>'
                  f'<div style="margin-top:14px;font-size:12px;">'
                  f'<div style="display:flex;justify-content:space-between;color:#546e7a;margin-bottom:4px;"><span>Subtotal</span><span></span></div>'
                  f'<div style="display:flex;justify-content:space-between;color:#c62828;font-weight:600;margin-bottom:4px;"><span>Descuento ({descuento:.0f}%)</span><span>-</span></div>'
                  f'<div style="display:flex;justify-content:space-between;color:#2e7d32;font-weight:700;font-size:14px;padding-top:6px;border-top:1px solid #e3eaf2;"><span>Total Final</span><span></span></div>'
                  f'</div></div>')
    else:
        bloque = f'<div style="background:#f0f4ff;border-left:4px solid #1565c0;border-radius:8px;padding:20px;margin-bottom:24px;"><div style="font-size:14px;font-weight:700;color:#1a237e;margin-bottom:8px;">{oferta.titulo}</div><div style="font-size:12px;color:#37474f;">{oferta.descripcion}</div></div>'
    html_body = f'''<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>Oferta Imprenta Tucan</title></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:Segoe UI,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:32px 0;"><tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.09);max-width:600px;width:100%;">
<tr><td style="background:linear-gradient(135deg,#1a3a5c,#1565c0);padding:36px 40px 28px;">
  <div style="font-size:13px;font-weight:600;color:rgba(255,255,255,.7);letter-spacing:1px;text-transform:uppercase;margin-bottom:10px;">Imprenta Tucan</div>
  <div style="font-family:Georgia,serif;font-size:28px;font-weight:700;color:#fff;line-height:1.2;margin-bottom:8px;">Combos con Descuento</div>
  <div style="font-size:13px;color:rgba(255,255,255,.65);">Una oferta preparada especialmente para vos</div>
</td></tr>
<tr><td style="padding:32px 40px;">
  <p style="font-size:14px;color:#37474f;margin:0 0 20px;">Hola <strong>{nombre}</strong>,</p>
  <p style="font-size:13px;color:#546e7a;margin:0 0 24px;line-height:1.6;">En <strong>Imprenta Tucan</strong> preparamos una oferta personalizada basada en tus pedidos anteriores.</p>
  {bloque}
  <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:28px;"><tr><td align="center">
    <a href="{link_aceptar}" style="display:inline-block;background:#22c55e;color:#fff;font-size:14px;font-weight:700;padding:13px 32px;border-radius:8px;text-decoration:none;margin-right:12px;">Aceptar oferta</a>
    <a href="{link_rechazar}" style="display:inline-block;background:#ef4444;color:#fff;font-size:14px;font-weight:700;padding:13px 32px;border-radius:8px;text-decoration:none;">Rechazar</a>
  </td></tr></table>
  <p style="text-align:center;margin-top:16px;"><a href="{link_ver}" style="font-size:12px;color:#1565c0;text-decoration:none;">Ver detalle completo</a></p>
</td></tr>
<tr><td style="background:#f8fafc;border-top:1px solid #e8edf2;padding:20px 40px;text-align:center;">
  <p style="font-size:11px;color:#90a4ae;margin:0;">Imprenta Tucan - info@imprenta.com.ar</p>
</td></tr>
</table></td></tr></table>{pixel}</body></html>'''
    try:
        send_mail(subject=f'Tu oferta personalizada - {oferta.titulo}', message='',
                  from_email=getattr(settings,'DEFAULT_FROM_EMAIL','no-reply@imprenta.local'),
                  recipient_list=[cliente.email], fail_silently=False, html_message=html_body)
        return True, None
    except Exception as e:
        return False, str(e)
