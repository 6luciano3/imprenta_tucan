# automatizacion/services.py
from django.conf import settings

def _html_tabla_combo(combo):
    filas = ''
    for cop in combo.comboofertaproducto_set.select_related('producto').all():
        precio = float(cop.producto.precioUnitario or 0)
        cant = int(cop.cantidad or 1)
        sub = precio * cant
        filas += (f'<tr>' + f'<td style="padding:9px 12px;border-bottom:1px solid #e8edf2;">{cop.producto.nombreProducto}</td>' + f'<td style="padding:9px 12px;text-align:center;">{cant}</td>' + '<td style="padding:9px 12px;text-align:right;">$' + "{:,.0f}".format(precio).replace(",",".") + '</td>' + '<td style="padding:9px 12px;text-align:right;font-weight:600;">$' + "{:,.0f}".format(sub).replace(",",".") + '</td></tr>')
    subtotal = sum(float(c.producto.precioUnitario or 0)*int(c.cantidad or 1) for c in combo.comboofertaproducto_set.select_related('producto').all())
    descuento = float(combo.descuento or 0)
    descuento_valor = subtotal * descuento / 100
    return filas, subtotal, descuento, descuento_valor, subtotal - descuento_valor

def enviar_oferta_email(oferta, request=None, force=False):
    """
    Envía email de oferta al cliente.
    
    Args:
        oferta: Instancia de OfertaPropuesta
        request: Objeto request de Django (opcional)
        force: Si True, ignora la verificación de email (para desarrollo/pruebas)
    """
    from django.conf import settings
    
    # Si force=True, omitir verificaciones de email
    if not force:
        force = getattr(settings, 'DEBUG', False)
    
    if not oferta.cliente or not oferta.cliente.email:
        return False, 'Cliente sin email definido'
    # Verificar que el email tiene formato valido
    import re
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', oferta.cliente.email):
        return False, f'Email invalido: {oferta.cliente.email}'
    # Verificar que el email fue verificado (omitir si force=True)
    if not force:
        if not getattr(oferta.cliente, 'email_verificado', False):
            return False, f'Email no verificado: {oferta.cliente.email}'
    # En modo debug, permitir envío sin verificación
    if getattr(settings, 'DEBUG', False):
        force = True
    cliente = oferta.cliente
    if request:
        url_base = request.build_absolute_uri('/')[:-1]
    else:
        from configuracion.models import Parametro
        url_base = Parametro.get('SITE_URL', 'http://localhost:8000').rstrip('/')
    token = oferta.token_email or ''
    link_aceptar  = f'{url_base}/automatizacion/oferta/{token}/aceptar/'
    link_rechazar = f'{url_base}/automatizacion/oferta/{token}/rechazar/'
    link_ver      = f'{url_base}/automatizacion/oferta/{token}/'
    pixel = f'<img src="{url_base}/automatizacion/acciones/pixel/?cliente_id={cliente.id}&oferta_id={oferta.id}&tipo=leido&canal=email" width="1" height="1" style="display:none;" alt="" />'
    nombre = getattr(cliente,'nombre','') or getattr(cliente,'razon_social','') or 'Cliente'
    from automatizacion.views_combos import generar_combo_para_cliente
    combo = generar_combo_para_cliente(cliente)
    descuento_oferta = float(oferta.parametros.get('descuento', 0)) if oferta.parametros else 0
    if combo and combo.comboofertaproducto_set.exists():
        filas, subtotal, descuento, desc_valor, total = _html_tabla_combo(combo)
        if descuento_oferta > 0:
            descuento = descuento_oferta
            descuento_valor = subtotal * descuento / 100
            total = subtotal - descuento_valor
            desc_valor = descuento_valor
        subtotal_str  = '${}'.format("{:,.0f}".format(subtotal).replace(',', '.'))
        desc_val_str = '${}'.format("{:,.0f}".format(desc_valor).replace(',', '.'))
        total_str    = '${}'.format("{:,.0f}".format(total).replace(',', '.'))
        bloque = (
            f'<div style="background:#f9fafc;border-radius:12px;border:1px solid #e3eaf2;padding:24px;margin-bottom:24px;">'
            f'<div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#1a237e;margin-bottom:6px;">{combo.nombre}</div>'
            f'<div style="font-size:12px;color:#607d8b;margin-bottom:16px;">{combo.descripcion}</div>'
            f'<table style="width:100%;border-collapse:collapse;font-size:12px;">'
            f'<thead><tr style="background:#1565c0;color:#fff;"><th style="padding:10px 12px;text-align:left;">Producto</th><th style="padding:10px 12px;text-align:center;">Cant.</th><th style="padding:10px 12px;text-align:right;">P.Unit.</th><th style="padding:10px 12px;text-align:right;">Subtotal</th></tr></thead>'
            f'<tbody>{filas}</tbody></table>'
            f'<div style="margin-top:14px;font-size:12px;">'
            f'<div style="display:flex;justify-content:space-between;color:#546e7a;margin-bottom:4px;"><span>Subtotal</span><span>{subtotal_str}</span></div>'
            f'<div style="display:flex;justify-content:space-between;color:#c62828;font-weight:600;margin-bottom:4px;"><span>Descuento ({descuento:.0f}%)</span><span>-{desc_val_str}</span></div>'
            f'<div style="display:flex;justify-content:space-between;color:#2e7d32;font-weight:700;font-size:14px;padding-top:6px;border-top:1px solid #e3eaf2;"><span>Total Final</span><span>{total_str}</span></div>'
            f'</div></div>'
        )
    else:
        bloque = f'<div style="background:#f0f4ff;border-left:4px solid #1565c0;border-radius:8px;padding:20px;margin-bottom:24px;"><div style="font-size:14px;font-weight:700;color:#1a237e;margin-bottom:8px;">{oferta.titulo}</div><div style="font-size:12px;color:#37474f;">{oferta.descripcion}</div></div>'
    
    # Botones de acción para el email de ofertas
    botones_html = f'''
    <tr><td style="padding:24px 28px;text-align:center;background:#f8fafc;border-top:1px solid #e2e8f0;">
        <div style="font-size:13px;color:#64748b;margin-bottom:16px;">¿Te interesa esta oferta? Respondé con un click:</div>
        <a href="{link_aceptar}" style="display:inline-block;background:#22c55e;color:#fff;font-size:14px;font-weight:700;padding:14px 32px;border-radius:8px;text-decoration:none;margin-right:12px;">✓ ACEPTAR OFERTA</a>
        <a href="{link_rechazar}" style="display:inline-block;background:#6b7280;color:#fff;font-size:14px;font-weight:700;padding:14px 32px;border-radius:8px;text-decoration:none;">✗ RECHAZAR</a>
    </td></tr>
    '''
    
    # Template simplificado para email de ofertas
    html_body = f'''
    <!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
    <title>Oferta Especial - Imprenta Tucán</title></head>
    <body style="margin:0;padding:0;background:#f0f4f8;font-family:Segoe UI,Arial,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:32px 0;">
    <tr><td align="center">
    <table width="620" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.09);max-width:620px;width:100%;">
    <tr><td style="background:#1e40af;padding:20px 28px;">
    <div style="font-size:11px;font-weight:600;color:rgba(255,255,255,.6);letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">Oferta Personalizada</div>
    <div style="font-size:22px;font-weight:700;color:#fff;">¡{nombre}, tenemos una oferta especial para vos!</div>
    </td></tr>
    <tr><td style="padding:24px 28px;border-bottom:1px solid #e2e8f0;">
    {bloque}
    </td></tr>
    {botones_html}
    <tr><td style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:14px 28px;text-align:center;">
    <div style="font-size:11px;color:#94a3b8;">Imprenta Tucán — www.imprentatucan.com.ar</div>
    </td></tr>
    </table></td></tr></table>
    {pixel}
    </body></html>
    '''
    mensaje_texto = f'Hola {nombre}, tenés una oferta personalizada de Imprenta Tucan. Visitá: {link_ver}'
    asunto = f'Oferta especial #{oferta.id} - Imprenta Tucán'
    try:
        from core.notifications.engine import enviar_notificacion
        from automatizacion.models import MensajeOferta
        import time

        # Canal principal: email - enviar solo a correos reales si score >= 96
        SCORE_MINIMO = 96
        EMAILS_DEMOSTRACION = ['bookdesignpdas@yahoo.com.ar', '6luciano10@gmail.com']
        
        score = getattr(oferta, 'score_al_generar', 0) or 0
        if score >= SCORE_MINIMO:
            # Alternar entre los dos emails de demostración
            indice = int(oferta.id) % len(EMAILS_DEMOSTRACION)
            canal_email = EMAILS_DEMOSTRACION[indice]
            canales: list[tuple[str, str]] = [('email', canal_email)]
        else:
            # Score bajo: no enviar (para demos rápidas)
            canales = []

        # Solo agregar canales adicionales si hay email configurado
        if canales:
            wa = getattr(cliente, 'numero_whatsapp', None)
            if wa:
                canales.append(('whatsapp', wa))
            tel_e164 = getattr(cliente, 'telefono_e164', None)
            if tel_e164:
                canales.append(('sms', tel_e164))

        ultimo_ok, ultimo_err = False, 'Sin canales configurados'
        for canal, destinatario in canales:
            try:
                res = {'ok': False, 'error': 'Sin intentos'}
                for intento in range(3):
                    try:
                        res = enviar_notificacion(
                            destinatario=destinatario,
                            mensaje=mensaje_texto,
                            canal=canal,
                            asunto=asunto,
                            html=html_body if canal == 'email' else None,
                            metadata={'oferta_id': oferta.id},
                        )
                        if res.get('ok'):
                            break
                    except Exception as e:
                        res = {'ok': False, 'error': str(e)}
                    if intento < 2:
                        time.sleep(2)
                MensajeOferta.objects.create(
                    oferta=oferta,
                    cliente=cliente,
                    estado='enviado' if res.get('ok') else 'fallido',
                    canal=canal,
                    detalle='Enviado por enviar_oferta_email()' if res.get('ok') else (res.get('error') or ''),
                )
                if res.get('ok'):
                    ultimo_ok, ultimo_err = True, None
            except Exception as exc:
                ultimo_err = str(exc)

        return ultimo_ok, ultimo_err
    except Exception as e:
        return False, str(e)


def generar_combo_para_cliente(cliente):
    """
    Proxy de servicio — delega a views_combos.
    Usado por core/ai_ml/ofertas.py para evitar que el dominio importe
    directamente desde una capa de presentación (views_*).
    """
    from automatizacion.views_combos import generar_combo_para_cliente as _fn
    return _fn(cliente)


def enviar_email_orden_compra_proveedor(orden_compra):
    """
    Envía un email al proveedor notificándole que se le asignó una nueva orden de compra,
    con botones para confirmar o rechazar directamente desde el email (sin login).
    Retorna (True, None) si se envió correctamente, o (False, mensaje_error) si falló.
    """
    proveedor = orden_compra.proveedor
    if not proveedor or not proveedor.email:
        return False, 'El proveedor no tiene email configurado'

    # Asegurar que la orden tiene token generado
    if not orden_compra.token_proveedor:
        import uuid
        orden_compra.token_proveedor = uuid.uuid4().hex
        orden_compra.save(update_fields=['token_proveedor'])

    from_email = getattr(settings, 'EMAIL_HOST_USER', getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@imprenta.local'))
    from configuracion.models import Parametro
    url_base = Parametro.get('SITE_URL', 'http://localhost:8000').rstrip('/')

    token = orden_compra.token_proveedor
    link_confirmar = f'{url_base}/proveedores/orden/{token}/confirmar/'
    link_rechazar  = f'{url_base}/proveedores/orden/{token}/rechazar/'

    # compras.OrdenCompra usa detalles (M:N con insumos) en lugar de un campo insumo directo
    detalles = list(orden_compra.detalles.select_related('insumo').all())

    estado = orden_compra.estado.nombre if hasattr(orden_compra.estado, 'nombre') else str(orden_compra.estado)
    comentario = getattr(orden_compra, 'observaciones', None) or getattr(orden_compra, 'comentario', None) or '—'
    fecha = orden_compra.fecha_creacion.strftime('%d/%m/%Y %H:%M') if orden_compra.fecha_creacion else '—'

    def _unidad_str(insumo):
        unidad_raw = getattr(insumo, 'unidad_medida', None)
        if unidad_raw and hasattr(unidad_raw, 'abreviatura'):
            return unidad_raw.abreviatura or 'unidad'
        return str(unidad_raw) if unidad_raw else 'unidad'

    html_body = (
        '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">'
        '<title>Solicitud de Cotizacion - Imprenta Tucan</title></head>'
        '<body style="margin:0;padding:0;background:#f0f4f8;font-family:Segoe UI,Arial,sans-serif;">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:32px 0;">'
        '<tr><td align="center">'
        '<table width="620" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.09);max-width:620px;width:100%;">'
        '<tr><td style="background:#334155;padding:20px 28px;">'
        '<div style="font-size:11px;font-weight:600;color:rgba(255,255,255,.6);letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">Solicitud de Cotización de Insumos</div>'
        f'<div style="font-size:22px;font-weight:700;color:#fff;">Nº {orden_compra.id:06d}</div>'
        '</td></tr>'
        '<tr><td style="padding:20px 28px;border-bottom:1px solid #e2e8f0;">'
        '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        '<td style="vertical-align:top;width:50%;">'
        '<div style="font-size:15px;font-weight:700;color:#1e293b;">Imprenta Tucán S.A.</div>'
        '<div style="font-size:12px;color:#64748b;margin-top:2px;">Av. Principal 123, Misiones</div>'
        '<div style="font-size:12px;color:#64748b;">IVA: Responsable Inscripto</div>'
        '</td>'
        '<td style="vertical-align:top;text-align:right;width:50%;">'
        '<div style="font-size:12px;color:#64748b;">Proveedor:</div>'
        f'<div style="font-size:14px;font-weight:700;color:#1e293b;">{proveedor.nombre}</div>'
        f'<div style="font-size:12px;color:#64748b;">CUIT: {proveedor.cuit or "-"}</div>'
        f'<div style="font-size:12px;color:#64748b;">{proveedor.direccion or "Dirección no especificada"}</div>'
        f'<div style="font-size:12px;color:#64748b;">{proveedor.email}</div>'
        '</td></tr></table>'
        '</td></tr>'
        '<tr><td style="padding:10px 28px;border-bottom:1px solid #e2e8f0;background:#f8fafc;">'
        '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="font-size:12px;color:#475569;"><strong>Fecha:</strong> {fecha}</td>'
        '<td style="font-size:12px;color:#475569;"><strong>Moneda:</strong> ARS</td>'
        f'<td style="font-size:12px;color:#475569;"><strong>Proveedor:</strong> {proveedor.nombre}</td>'
        '</tr></table>'
        '</td></tr>'
        '<tr><td style="padding:20px 28px;">'
        '<div style="font-size:13px;font-weight:600;color:#1e293b;margin-bottom:10px;">Detalle de Productos</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:12px;">'
        '<thead><tr style="background:#334155;color:#fff;">'
        '<th style="padding:8px 10px;text-align:left;border-right:1px solid #475569;">Código</th>'
        '<th style="padding:8px 10px;text-align:left;border-right:1px solid #475569;">Descripción</th>'
        '<th style="padding:8px 10px;text-align:center;border-right:1px solid #475569;">Cantidad solicitada</th>'
        '<th style="padding:8px 10px;text-align:center;">Unidad</th>'
        '</tr></thead><tbody>'
        + ''.join(
            f'<tr style="background:{"#f0f9ff" if i % 2 == 0 else "#fff"};">'
            f'<td style="border:1px solid #e2e8f0;padding:8px 10px;">{getattr(d.insumo, "codigo", "") or ""}</td>'
            f'<td style="border:1px solid #e2e8f0;padding:8px 10px;">{getattr(d.insumo, "nombre", str(d.insumo))}</td>'
            f'<td style="border:1px solid #e2e8f0;padding:8px 10px;text-align:center;">{d.cantidad}</td>'
            f'<td style="border:1px solid #e2e8f0;padding:8px 10px;text-align:center;">{_unidad_str(d.insumo)}</td>'
            '</tr>'
            for i, d in enumerate(detalles)
        )
        + '</tbody></table>'
        '</td></tr>'
        '<tr><td style="padding:16px 28px;border-top:1px solid #e2e8f0;">'
        '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        '<td style="vertical-align:top;width:50%;">'
        '<div style="font-size:13px;font-weight:600;margin-bottom:6px;">Entrega a:</div>'
        '<div style="font-size:12px;color:#475569;">Imprenta Tucán S.A.</div>'
        '<div style="font-size:12px;color:#475569;">Av. Principal 123, Misiones</div>'
        '<div style="font-size:12px;color:#475569;">Tel: 381-4000000</div>'
        '</td>'
        '<td style="vertical-align:top;text-align:right;width:50%;">'
        '<div style="font-size:12px;color:#475569;"><strong>Generado por:</strong> Sistema automático</div>'
        f'<div style="font-size:12px;color:#475569;"><strong>Fecha:</strong> {fecha}</div>'
        '</td></tr></table>'
        '</td></tr>'
        '<tr><td style="padding:16px 28px;border-top:1px solid #e2e8f0;">'
        '<table cellpadding="0" cellspacing="0"><tr>'
        '<td style="padding-right:40px;">'
        '<div style="height:32px;border-bottom:1px solid #94a3b8;width:120px;"></div>'
        '<div style="font-size:11px;color:#94a3b8;margin-top:4px;">Firma autorizada</div>'
        '</td><td>'
        '<div style="height:32px;border-bottom:1px solid #94a3b8;width:120px;"></div>'
        '<div style="font-size:11px;color:#94a3b8;margin-top:4px;">Cargo</div>'
        '</td></tr></table>'
        '</td></tr>'
        '<tr><td style="padding:20px 28px;border-top:1px solid #e2e8f0;text-align:center;">'
        '<div style="font-size:12px;color:#64748b;margin-bottom:14px;">Por favor confirme o rechace esta solicitud:</div>'
        f'<a href="{link_confirmar}" style="display:inline-block;background:#22c55e;color:#fff;font-size:13px;font-weight:700;padding:12px 28px;border-radius:8px;text-decoration:none;margin-right:12px;">✓ Confirmar orden</a>'
        f'<a href="{link_rechazar}" style="display:inline-block;background:#ef4444;color:#fff;font-size:13px;font-weight:700;padding:12px 28px;border-radius:8px;text-decoration:none;">✗ Rechazar orden</a>'
        '</td></tr>'
        '<tr><td style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:14px 28px;text-align:center;">'
        f'<div style="font-size:11px;color:#94a3b8;">Imprenta Tucán — {from_email}</div>'
        '</td></tr>'
        '</table></td></tr></table></body></html>'
    )

    lineas_insumos = '\n'.join(
        f"  - {getattr(d.insumo, 'nombre', str(d.insumo))} (x{d.cantidad} {_unidad_str(d.insumo)})"
        for d in detalles
    ) or '  (sin insumos)'
    texto_plano = (
        f"Nueva Orden de Compra - Imprenta Tucan\n\n"
        f"Estimado/a {proveedor.nombre},\n\n"
        f"Orden N°: #{orden_compra.id}\n"
        f"Insumos:\n{lineas_insumos}\n"
        f"Estado: {estado}\n"
        f"Fecha: {fecha}\n"
        f"Observaciones: {comentario}\n\n"
        f"Para CONFIRMAR la orden visite:\n{link_confirmar}\n\n"
        f"Para RECHAZAR la orden visite:\n{link_rechazar}\n\n"
        f"Imprenta Tucan"
    )

    try:
        from core.notifications.engine import enviar_notificacion
        
        # Enviar al proveedor
        resultado = enviar_notificacion(
            destinatario=proveedor.email,
            mensaje=texto_plano,
            canal='email',
            asunto=f'Nueva Orden de Compra #{orden_compra.id} — Imprenta Tucan',
            html=html_body,
            metadata={'orden_compra_id': orden_compra.id},
        )
        
        # PROCESO INTELIGENTE: Si está auto-aprobada, enviar copia a emails de demostración
        EMAILS_DEMOSTRACION = ['bookdesignpdas@yahoo.com.ar', '6luciano10@gmail.com']
        if orden_compra.estado == 'confirmada' and '[AUTO-APROBADO]' in (orden_compra.comentario or ''):
            for email_demo in EMAILS_DEMOSTRACION:
                try:
                    enviar_notificacion(
                        destinatario=email_demo,
                        mensaje=texto_plano,
                        canal='email',
                        asunto=f'[COPIA] Orden Compra #{orden_compra.id} — {proveedor.nombre}',
                        html=html_body,
                        metadata={'orden_compra_id': orden_compra.id, 'copia_demo': True},
                    )
                except Exception:
                    pass
        
        return resultado['ok'], resultado.get('error')
    except Exception as e:
        return False, str(e)

def enviar_solicitud_cotizacion(proveedor, insumos_cantidades, comentario=''):
    """
    Crea una SolicitudCotizacion agrupando multiples insumos y envia un solo email al proveedor.
    insumos_cantidades: lista de tuplas (insumo, cantidad)
    Retorna (SolicitudCotizacion, ok, err)
    """
    from automatizacion.models import SolicitudCotizacion, SolicitudCotizacionItem
    from configuracion.models import Parametro
    from django.conf import settings as dj_settings

    if not proveedor.email or proveedor.email.endswith('.local'):
        return None, False, 'Proveedor sin email real'

    from_email = getattr(dj_settings, 'EMAIL_HOST_USER', getattr(dj_settings, 'DEFAULT_FROM_EMAIL', 'no-reply@imprenta.local'))
    url_base = Parametro.get('SITE_URL', 'http://localhost:8000').rstrip('/')

    try:
        sc = SolicitudCotizacion.objects.create(
            proveedor=proveedor,
            comentario=comentario,
        )
        for insumo, cantidad in insumos_cantidades:
            SolicitudCotizacionItem.objects.create(
                solicitud=sc,
                insumo=insumo,
                cantidad=cantidad,
            )

        link_confirmar = f'{url_base}/automatizacion/solicitud-cotizacion/{sc.token}/confirmar/'
        link_rechazar  = f'{url_base}/automatizacion/solicitud-cotizacion/{sc.token}/rechazar/'

        # Construir filas de la tabla
        filas_html = ''
        for idx, item in enumerate(sc.items.select_related('insumo').all()):
            bg = '#f0f9ff' if idx % 2 == 0 else '#fff'
            insumo = item.insumo
            codigo = getattr(insumo, 'codigo', '') or ''
            nombre = getattr(insumo, 'nombre', str(insumo))
            unidad_raw = getattr(insumo, 'unidad_medida', None)
            if unidad_raw and hasattr(unidad_raw, 'abreviatura'):
                unidad = unidad_raw.abreviatura or 'unidad'
            elif unidad_raw:
                unidad = str(unidad_raw)
            else:
                unidad = 'unidad'
            filas_html += (
                f'<tr style="background:{bg};">'
                f'<td style="border:1px solid #e2e8f0;padding:8px 10px;">{codigo}</td>'
                f'<td style="border:1px solid #e2e8f0;padding:8px 10px;">{nombre}</td>'
                f'<td style="border:1px solid #e2e8f0;padding:8px 10px;text-align:center;">{item.cantidad}</td>'
                f'<td style="border:1px solid #e2e8f0;padding:8px 10px;text-align:center;">{unidad}</td>'
                f'</tr>'
            )

        from django.utils import timezone
        fecha_str = timezone.now().strftime('%d/%m/%Y')

        html_body = (
            '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">'
            '<title>Solicitud de Cotizacion - Imprenta Tucan</title></head>'
            '<body style="margin:0;padding:0;background:#f0f4f8;font-family:Segoe UI,Arial,sans-serif;">'
            '<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:32px 0;">'
            '<tr><td align="center">'
            '<table width="620" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.09);max-width:620px;width:100%;">'
            '<tr><td style="background:#334155;padding:20px 28px;">'
            '<div style="font-size:11px;font-weight:600;color:rgba(255,255,255,.6);letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">Solicitud de Cotización de Insumos</div>'
            f'<div style="font-size:22px;font-weight:700;color:#fff;">Nº {sc.id:06d}</div>'
            '</td></tr>'
            '<tr><td style="padding:20px 28px;border-bottom:1px solid #e2e8f0;">'
            '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
            '<td style="vertical-align:top;width:50%;">'
            '<div style="font-size:15px;font-weight:700;color:#1e293b;">Imprenta Tucán S.A.</div>'
            '<div style="font-size:12px;color:#64748b;margin-top:2px;">Av. Principal 123, Misiones</div>'
            '<div style="font-size:12px;color:#64748b;">IVA: Responsable Inscripto</div>'
            '</td>'
            '<td style="vertical-align:top;text-align:right;width:50%;">'
            '<div style="font-size:12px;color:#64748b;">Proveedor:</div>'
            f'<div style="font-size:14px;font-weight:700;color:#1e293b;">{proveedor.nombre}</div>'
            f'<div style="font-size:12px;color:#64748b;">CUIT: {proveedor.cuit or "-"}</div>'
            f'<div style="font-size:12px;color:#64748b;">{proveedor.direccion or "Dirección no especificada"}</div>'
            f'<div style="font-size:12px;color:#64748b;">{proveedor.email}</div>'
            '</td></tr></table></td></tr>'
            '<tr><td style="padding:10px 28px;border-bottom:1px solid #e2e8f0;background:#f8fafc;">'
            '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="font-size:12px;color:#475569;"><strong>Fecha:</strong> {fecha_str}</td>'
            '<td style="font-size:12px;color:#475569;"><strong>Moneda:</strong> ARS</td>'
            f'<td style="font-size:12px;color:#475569;"><strong>Proveedor:</strong> {proveedor.nombre}</td>'
            '</tr></table></td></tr>'
            '<tr><td style="padding:20px 28px;">'
            '<div style="font-size:13px;font-weight:600;color:#1e293b;margin-bottom:10px;">Detalle de Productos</div>'
            '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:12px;">'
            '<thead><tr style="background:#334155;color:#fff;">'
            '<th style="padding:8px 10px;text-align:left;border-right:1px solid #475569;">Código</th>'
            '<th style="padding:8px 10px;text-align:left;border-right:1px solid #475569;">Descripción</th>'
            '<th style="padding:8px 10px;text-align:center;border-right:1px solid #475569;">Cantidad solicitada</th>'
            '<th style="padding:8px 10px;text-align:center;">Unidad</th>'
            '</tr></thead><tbody>'
            + filas_html +
            '</tbody></table></td></tr>'
            '<tr><td style="padding:16px 28px;border-top:1px solid #e2e8f0;">'
            '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
            '<td style="vertical-align:top;width:50%;">'
            '<div style="font-size:13px;font-weight:600;margin-bottom:6px;">Entrega a:</div>'
            '<div style="font-size:12px;color:#475569;">Imprenta Tucán S.A.</div>'
            '<div style="font-size:12px;color:#475569;">Av. Principal 123, Misiones</div>'
            '<div style="font-size:12px;color:#475569;">Tel: 381-4000000</div>'
            '</td>'
            '<td style="vertical-align:top;text-align:right;width:50%;">'
            f'<div style="font-size:12px;color:#475569;"><strong>Generado por:</strong> Sistema automático</div>'
            f'<div style="font-size:12px;color:#475569;"><strong>Fecha:</strong> {fecha_str}</div>'
            '</td></tr></table></td></tr>'
            '<tr><td style="padding:16px 28px;border-top:1px solid #e2e8f0;">'
            '<table cellpadding="0" cellspacing="0"><tr>'
            '<td style="padding-right:40px;"><div style="height:32px;border-bottom:1px solid #94a3b8;width:120px;"></div>'
            '<div style="font-size:11px;color:#94a3b8;margin-top:4px;">Firma autorizada</div></td>'
            '<td><div style="height:32px;border-bottom:1px solid #94a3b8;width:120px;"></div>'
            '<div style="font-size:11px;color:#94a3b8;margin-top:4px;">Cargo</div></td>'
            '</tr></table></td></tr>'
            '<tr><td style="padding:20px 28px;border-top:1px solid #e2e8f0;text-align:center;">'
            '<div style="font-size:12px;color:#64748b;margin-bottom:14px;">Por favor confirme o rechace esta solicitud:</div>'
            f'<a href="{link_confirmar}" style="display:inline-block;background:#22c55e;color:#fff;font-size:13px;font-weight:700;padding:12px 28px;border-radius:8px;text-decoration:none;margin-right:12px;">✓ Confirmar</a>'
            f'<a href="{link_rechazar}" style="display:inline-block;background:#ef4444;color:#fff;font-size:13px;font-weight:700;padding:12px 28px;border-radius:8px;text-decoration:none;">✗ Rechazar</a>'
            '</td></tr>'
            '<tr><td style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:14px 28px;text-align:center;">'
            f'<div style="font-size:11px;color:#94a3b8;">Imprenta Tucán — {from_email}</div>'
            '</td></tr>'
            '</table></td></tr></table></body></html>'
        )

        texto_plano = (
            f'Solicitud de Cotizacion SC-{sc.id:04d} - Imprenta Tucan\n'
            f'Proveedor: {proveedor.nombre}\n'
            f'Confirmar: {link_confirmar}\n'
            f'Rechazar: {link_rechazar}'
        )

        asunto = f'Solicitud de Cotizacion SC-{sc.id:04d} - Imprenta Tucan'

        from django.core.mail import EmailMultiAlternatives
        msg = EmailMultiAlternatives(asunto, texto_plano, from_email, [proveedor.email])
        msg.attach_alternative(html_body, "text/html")
        msg.send()
        return sc, True, None

    except Exception as e:
        import traceback
        return None, False, str(e) + '\n' + traceback.format_exc()
