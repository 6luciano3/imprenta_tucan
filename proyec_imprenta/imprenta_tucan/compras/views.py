from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import OrdenCompra, DetalleOrdenCompra, Remito, DetalleRemito, EstadoCompra
from .forms import OrdenCompraForm, DetalleOrdenCompraFormSet, RemitoForm, DetalleRemitoFormSet


def _datos_empresa() -> dict:
    """Lee los datos de la empresa desde configuracion.Parametro (con fallback)."""
    try:
        from configuracion.models import Parametro
        return {
            'nombre':   Parametro.get('EMPRESA_NOMBRE',    'Imprenta Tucán S.A.'),
            'cuit':     Parametro.get('EMPRESA_CUIT',      ''),
            'domicilio':Parametro.get('EMPRESA_DOMICILIO', ''),
            'telefono': Parametro.get('EMPRESA_TELEFONO',  ''),
            'email':    Parametro.get('EMPRESA_EMAIL',     ''),
            'iva':      Parametro.get('EMPRESA_CONDICION_IVA', 'Responsable Inscripto'),
        }
    except Exception:
        return {
            'nombre': 'Imprenta Tucán S.A.',
            'cuit': '', 'domicilio': '', 'telefono': '', 'email': '',
            'iva': 'Responsable Inscripto',
        }


def _registrar_auditoria(request, instance, action="create"):
    try:
        from auditoria.models import AuditEntry
        AuditEntry.objects.create(
            user=request.user if request.user.is_authenticated else None,
            app_label="compras",
            model=instance.__class__.__name__,
            object_id=str(instance.pk),
            object_repr=str(instance),
            action=action,
            ip_address=request.META.get("REMOTE_ADDR"),
            path=request.path,
            method=request.method,
        )
    except Exception:
        pass


# ── Ordenes de Compra ─────────────────────────────────────────────────────────

@login_required
def lista_ordenes(request):
    from django.core.paginator import Paginator, EmptyPage
    from django.db import models
    from proveedores.models import Proveedor
    
    ordenes = OrdenCompra.objects.select_related("proveedor", "estado", "usuario").prefetch_related("detalles__insumo")
    
    # Filtros
    proveedor_id = request.GET.get('proveedor')
    estado_id = request.GET.get('estado')
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    buscar = request.GET.get('buscar')
    
    if proveedor_id:
        ordenes = ordenes.filter(proveedor_id=proveedor_id)
    if estado_id:
        ordenes = ordenes.filter(estado_id=estado_id)
    if fecha_desde:
        ordenes = ordenes.filter(fecha_creacion__gte=fecha_desde)
    if fecha_hasta:
        ordenes = ordenes.filter(fecha_creacion__lte=fecha_hasta)
    if buscar:
        ordenes = ordenes.filter(
            models.Q(pk__icontains=buscar) |
            models.Q(proveedor__nombre__icontains=buscar)
        )
    
    # Resumen de estados
    resumen_estados = []
    for estado in EstadoCompra.objects.all():
        count = OrdenCompra.objects.filter(estado=estado).count()
        if count > 0:
            resumen_estados.append({
                'nombre': estado.nombre,
                'count': count,
                'id': estado.pk,
            })
    
    # Paginación
    paginator = Paginator(ordenes, 15)
    page = request.GET.get('page', 1)
    try:
        ordenes_page = paginator.page(page)
    except EmptyPage:
        ordenes_page = paginator.page(paginator.num_pages)
    
    proveedores = Proveedor.objects.filter(activo=True).order_by('nombre')
    estados = EstadoCompra.objects.all()
    
    return render(request, "compras/lista_ordenes.html", {
        "ordenes": ordenes_page,
        "proveedores": proveedores,
        "estados": estados,
        "resumen_estados": resumen_estados,
        "buscar": buscar or '',
    })


@login_required
def nueva_orden(request):
    if request.method == "POST":
        form = OrdenCompraForm(request.POST)
        formset = DetalleOrdenCompraFormSet(request.POST, prefix="detalles")
        if form.is_valid() and formset.is_valid():
            orden = form.save(commit=False)
            orden.usuario = request.user
            orden.save()
            total = 0
            for df in formset:
                if df.cleaned_data and not df.cleaned_data.get("DELETE", False):
                    detalle = DetalleOrdenCompra.objects.create(
                        orden=orden,
                        insumo=df.cleaned_data["insumo"],
                        cantidad=df.cleaned_data["cantidad"],
                        precio_unitario=df.cleaned_data["precio_unitario"],
                    )
                    total += detalle.subtotal()
            orden.monto_total = total
            orden.save(update_fields=["monto_total"])
            _registrar_auditoria(request, orden, "create")
            messages.success(request, f"Orden de compra OC-{orden.pk:04d} creada correctamente.")
            return redirect('compras:lista_ordenes_compra')
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        form = OrdenCompraForm()
        formset = DetalleOrdenCompraFormSet(prefix="detalles")
    return render(request, "compras/nueva_orden.html", {"form": form, "formset": formset})


@login_required
def detalle_orden(request, pk):
    orden = get_object_or_404(OrdenCompra.objects.select_related("proveedor", "estado", "usuario").prefetch_related("detalles__insumo", "remitos"), pk=pk)
    return render(request, "compras/detalle_orden.html", {"orden": orden})


@login_required
def detalle_orden_json(request, pk):
    from django.http import JsonResponse
    orden = get_object_or_404(OrdenCompra.objects.select_related("proveedor", "estado").prefetch_related("detalles__insumo"), pk=pk)
    
    # Recalcular monto_total si es 0 pero hay detalles
    if orden.monto_total == 0:
        total = sum(d.subtotal() for d in orden.detalles.all())
        if total > 0:
            orden.monto_total = total
            orden.save(update_fields=["monto_total"])
    
    detalles = []
    for d in orden.detalles.all():
        codigo = getattr(d.insumo, 'codigo', None) or f"IN-{d.insumo.pk:03d}"
        detalles.append({
            'codigo': codigo,
            'insumo': d.insumo.nombre,
            'cantidad': d.cantidad,
            'unidad': getattr(d.insumo, 'unidad_medida', None) or 'un',
            'precio': float(d.precio_unitario),
            'subtotal': float(d.subtotal()),
        })
    
    subtotal = float(orden.monto_total)
    iva = subtotal * 0.21
    total = subtotal + iva
    
    # Obtener texto de condición de pago
    condicion_pago_text = dict(OrdenCompra.CONDICIONES_PAGO).get(orden.condicion_pago, 'Contado')
    
    return JsonResponse({
        'id': orden.pk,
        'fecha': orden.fecha_creacion.strftime('%d/%m/%Y'),
        'fecha_entrega': orden.fecha_entrega.strftime('%d/%m/%Y') if orden.fecha_entrega else '',
        'fecha_recepcion': orden.fecha_recepcion.strftime('%d/%m/%Y') if orden.fecha_recepcion else '',
        'estado': orden.estado.nombre if orden.estado else '',
        'enviada': orden.enviada,
        'fecha_envio': orden.fecha_envio.strftime('%d/%m/%Y %H:%M') if orden.fecha_envio else '',
        
        # Empresa
        'empresa': _datos_empresa(),
        
        # Proveedor
        'proveedor': {
            'nombre': orden.proveedor.nombre,
            'cuit': orden.proveedor.cuit or '',
            'direccion': orden.proveedor.direccion or '',
            'contacto': orden.proveedor.telefono or '',
            'email': orden.proveedor.email or '',
        },
        
        # Condiciones
        'condicion_pago': condicion_pago_text,
        'moneda': 'ARS',
        'entrega': 'Depósito Gráfica Tucán',
        'observaciones': orden.observaciones or '',
        
        # Totales
        'subtotal': subtotal,
        'iva': iva,
        'total': total,
        
        'detalles': detalles,
    })


@require_POST
@login_required
def enviar_orden_email(request, pk):
    from django.core.mail import send_mail
    from django.conf import settings
    
    orden = get_object_or_404(OrdenCompra.objects.select_related("proveedor").prefetch_related("detalles__insumo"), pk=pk)
    proveedor = orden.proveedor
    
    if not proveedor.email:
        return JsonResponse({'ok': False, 'error': 'Proveedor sin email'}, status=400)
    
    if orden.monto_total == 0:
        total = sum(d.subtotal() for d in orden.detalles.all())
        if total > 0:
            orden.monto_total = total
            orden.save(update_fields=["monto_total"])
    
    subtotal = float(orden.monto_total)
    iva = subtotal * 0.21
    total = subtotal + iva
    condicion_pago_text = dict(OrdenCompra.CONDICIONES_PAGO).get(orden.condicion_pago, 'Contado')
    empresa = _datos_empresa()

    detalles_html = ""
    num = 1
    for d in orden.detalles.all():
        codigo = getattr(d.insumo, 'codigo', None) or f"IN-{d.insumo.pk:03d}"
        unidad = getattr(d.insumo, 'unidad_medida', None) or 'un'
        detalles_html += f"""
        <tr style="border-bottom: 1px solid #eee;">
            <td style="padding: 8px; text-align: center; color: #666;">{num}</td>
            <td style="padding: 8px; color: #333;">{codigo}</td>
            <td style="padding: 8px; color: #333;">{d.insumo.nombre}</td>
            <td style="padding: 8px; text-align: center; color: #333;">{d.cantidad}</td>
            <td style="padding: 8px; text-align: center; color: #333;">{unidad}</td>
            <td style="padding: 8px; text-align: right; color: #333;">$ {float(d.precio_unitario):.2f}</td>
            <td style="padding: 8px; text-align: right; font-weight: bold; color: #333;">$ {float(d.subtotal()):.2f}</td>
        </tr>
        """
        num += 1
    
    dominio = request.get_host()
    protocolo = 'http' if 'localhost' in dominio or '127.0.0.1' in dominio else 'https'
    url_verificar = f"{protocolo}://{dominio}/compras/ordenes/{orden.pk}/"
    
    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }}
            .container {{ max-width: 700px; margin: 0 auto; background: white; }}
            .header {{ background: #2563eb; color: white; padding: 20px; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header .orden-num {{ font-size: 18px; margin-top: 5px; }}
            .content {{ padding: 20px; }}
            .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px; }}
            .info-box {{ background: #f8f9fa; padding: 12px; border-radius: 8px; }}
            .info-box h4 {{ margin: 0 0 8px 0; color: #666; font-size: 11px; text-transform: uppercase; }}
            .info-box p {{ margin: 0; color: #333; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th {{ background: #f3f4f6; padding: 10px; text-align: left; font-size: 11px; color: #666; text-transform: uppercase; }}
            .totals {{ margin-top: 20px; text-align: right; }}
            .totals .row {{ display: flex; justify-content: flex-end; gap: 30px; padding: 5px 0; }}
            .totals .total {{ font-size: 18px; font-weight: bold; color: #16a34a; border-top: 2px solid #333; padding-top: 10px; }}
            .observaciones {{ background: #f8f9fa; padding: 12px; border-radius: 8px; margin-top: 20px; }}
            .botones {{ padding: 20px; text-align: center; background: #f5f5f5; }}
            .btn {{ display: inline-block; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; margin: 5px; }}
            .btn-primary {{ background: #2563eb; color: white; }}
            .btn-success {{ background: #16a34a; color: white; }}
            .btn-warning {{ background: #f59e0b; color: white; }}
            .footer {{ text-align: center; padding: 15px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{empresa['nombre'].upper()}</h1>
                <div class="orden-num">ORDEN DE COMPRA Nº {orden.pk:04d}</div>
            </div>
            
            <div class="content">
                <div class="info-grid">
                    <div class="info-box">
                        <h4>Fecha de Emisión</h4>
                        <p>{orden.fecha_creacion.strftime('%d/%m/%Y')}</p>
                    </div>
                    <div class="info-box">
                        <h4>Condición de Pago</h4>
                        <p>{condicion_pago_text}</p>
                    </div>
                    <div class="info-box">
                        <h4>Moneda</h4>
                        <p>ARS</p>
                    </div>
                    <div class="info-box">
                        <h4>Fecha Entrega</h4>
                        <p>{orden.fecha_recepcion.strftime('%d/%m/%Y') if orden.fecha_recepcion else 'A convenir'}</p>
                    </div>
                </div>
                
                <div class="info-box">
                    <h4>Proveedor</h4>
                    <p style="font-weight: bold;">{proveedor.nombre}</p>
                    <p>CUIT: {proveedor.cuit or ' - '}</p>
                    <p>{proveedor.direccion or ''}</p>
                    <p>Tel: {proveedor.telefono or ''} | Email: {proveedor.email}</p>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Código</th>
                            <th>Descripción</th>
                            <th>Cant.</th>
                            <th>Unidad</th>
                            <th>P. Unit.</th>
                            <th>Subtotal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {detalles_html}
                    </tbody>
                </table>
                
                <div class="totals">
                    <div class="row"><span>Subtotal:</span><span>$ {subtotal:.2f}</span></div>
                    <div class="row"><span>IVA 21%:</span><span>$ {iva:.2f}</span></div>
                    <div class="row total"><span>TOTAL:</span><span>$ {total:.2f}</span></div>
                </div>
                
                <div class="observaciones">
                    <h4 style="margin: 0 0 8px 0; color: #666; font-size: 11px; text-transform: uppercase;">Condiciones de Entrega</h4>
                    <p><strong>Lugar:</strong> {empresa['domicilio'] or 'A convenir'}</p>
                    <p><strong>Observaciones:</strong> {orden.observaciones or 'Sin observaciones'}</p>
                </div>
            </div>
            
            <div class="botones">
                <p style="margin-bottom: 15px; color: #666;">¿Qué deseas hacer con esta orden?</p>
                <a href="{url_verificar}" class="btn btn-primary">VER EN WEB</a>
                <a href="{url_verificar}confirmar/" class="btn btn-success">CONFIRMAR ORDEN</a>
                <a href="{url_verificar}rechazar/" class="btn btn-warning">RECHAZAR</a>
            </div>
            
            <div class="footer">
                <p>{empresa['nombre']} | {empresa['email']} | {empresa['telefono']}</p>
                <p>Este es un mensaje automático. Por favor no responder a este email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        send_mail(
            subject=f'Orden de Compra OC-{orden.pk:04d} - {empresa["nombre"]}',
            message='Orden de Compra',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[proveedor.email],
            html_message=html_message,
            fail_silently=False,
        )
        # Marcar orden como enviada
        from django.utils import timezone
        orden.enviada = True
        orden.fecha_envio = timezone.now()
        orden.save(update_fields=['enviada', 'fecha_envio'])
        return JsonResponse({'ok': True, 'message': 'Email enviado'})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


def confirmar_orden_publico(request, pk):
    from django.utils import timezone
    from django.db import transaction
    
    orden = get_object_or_404(OrdenCompra.objects.prefetch_related("detalles"), pk=pk)
    
    try:
        with transaction.atomic():
            # 1. Cambiar estado a confirmada
            estado_confirmado = EstadoCompra.objects.get(nombre__icontains='confirmado')
            orden.estado = estado_confirmado
            
            # 2. Crear remito automáticamente
            from .models import Remito, DetalleRemito, MovimientoStock
            
            numero_remito = f"OC-{orden.pk:04d}"
            remito = Remito.objects.create(
                orden_compra=orden,
                proveedor=orden.proveedor,
                numero=numero_remito,
                fecha=timezone.now().date(),
                observaciones="Remito generado automáticamente al confirmar orden desde email del proveedor."
            )
            
            # 3. Registrar detalles y aumentar stock
            detalles_creados = []
            for detalle in orden.detalles.all():
                # Crear detalle del remito
                DetalleRemito.objects.create(
                    remito=remito,
                    insumo=detalle.insumo,
                    cantidad=detalle.cantidad
                )
                
                # Aumentar stock
                stock_anterior = detalle.insumo.stock or 0
                detalle.insumo.stock = stock_anterior + detalle.cantidad
                detalle.insumo.save(update_fields=['stock', 'updated_at'])
                
                # Registrar movimiento de stock (Kardex)
                MovimientoStock.objects.create(
                    insumo=detalle.insumo,
                    tipo="entrada",
                    origen="remito",
                    cantidad=detalle.cantidad,
                    stock_anterior=stock_anterior,
                    stock_posterior=detalle.insumo.stock,
                    referencia=f"Remito {remito.numero} (OC-{orden.pk:04d})",
                    remito=remito,
                    fecha=timezone.now().date(),
                )
                
                detalles_creados.append(f"{detalle.insumo.nombre} (+{detalle.cantidad})")
            
            # 4. Marcar orden como recibida
            orden.fecha_recepcion = timezone.now().date()
            orden.save(update_fields=['estado', 'fecha_recepcion', 'actualizado_en'])
            
            # 5. Enviar notificación interna
            try:
                from core.notifications.engine import enviar_notificacion
                enviar_notificacion(
                    titulo=f"OC-{orden.pk:04d} confirmada por proveedor",
                    mensaje=f"El proveedor {orden.proveedor.nombre} ha confirmado la orden de compra. Stock actualizado automáticamente.",
                    tipo="success",
                    importancia="alta",
                    enlace=f"/compras/ordenes/{orden.pk}/"
                )
            except Exception as e:
                pass  # No fallar si no se puede enviar notificación
            
            mensaje = f"Orden confirmada y mercadería recibida. Stock actualizado: {', '.join(detalles_creados[:3])}"
            if len(detalles_creados) > 3:
                mensaje += f" y {len(detalles_creados) - 3} más"
                
    except Exception as e:
        mensaje = f"Error al confirmar la orden: {str(e)}. Contacte a Imprenta Tucán."
    
    return render(request, "compras/respuesta_proveedor.html", {
        "orden": orden,
        "accion": "confirmada",
        "mensaje": mensaje,
    })


def rechazar_orden_publico(request, pk):
    orden = get_object_or_404(OrdenCompra, pk=pk)
    
    try:
        estado_rechazado = EstadoCompra.objects.get(nombre__icontains='rechazado')
        orden.estado = estado_rechazado
        orden.save(update_fields=['estado', 'actualizado_en'])
        
        # Enviar notificación interna
        try:
            from core.notifications.engine import enviar_notificacion
            enviar_notificacion(
                titulo=f"OC-{orden.pk:04d} rechazada por proveedor",
                mensaje=f"El proveedor {orden.proveedor.nombre} ha rechazado la orden de compra.",
                tipo="warning",
                importancia="alta",
                enlace=f"/compras/ordenes/{orden.pk}/"
            )
        except Exception:
            pass
        
        mensaje = "Orden rechazada. Si tiene alguna consulta, contacte a Imprenta Tucán."
    except EstadoCompra.DoesNotExist:
        mensaje = "Error al rechazar la orden. Contacte a Imprenta Tucán."
    
    return render(request, "compras/respuesta_proveedor.html", {
        "orden": orden,
        "accion": "rechazada",
        "mensaje": mensaje,
    })


@require_POST
@login_required
def enviar_orden_whatsapp(request, pk):
    import urllib.parse
    
    orden = get_object_or_404(OrdenCompra.objects.select_related("proveedor").prefetch_related("detalles__insumo"), pk=pk)
    proveedor = orden.proveedor
    
    telefono = proveedor.whatsapp or proveedor.telefono_e164 or proveedor.telefono
    
    if not telefono:
        return JsonResponse({'ok': False, 'error': 'Proveedor sin teléfono'}, status=400)
    
    telefono = telefono.replace('+', '').replace(' ', '').replace('-', '')
    if not telefono.startswith('54'):
        telefono = '54' + telefono
    
    if orden.monto_total == 0:
        total = sum(d.subtotal() for d in orden.detalles.all())
        if total > 0:
            orden.monto_total = total
            orden.save(update_fields=["monto_total"])
    
    subtotal = float(orden.monto_total)
    iva = subtotal * 0.21
    total = subtotal + iva
    
    mensaje = f"*ORDEN DE COMPRA*\n"
    mensaje += f"*Nº {orden.pk:04d}*\n\n"
    mensaje += f"*Fecha:* {orden.fecha_creacion.strftime('%d/%m/%Y')}\n\n"
    mensaje += f"*Proveedor:* {proveedor.nombre}\n\n"
    mensaje += f"*DETALLE:*\n"
    
    for d in orden.detalles.all():
        mensaje += f"• {d.cantidad} {getattr(d.insumo, 'unidad_medida', '') or 'un'} {d.insumo.nombre} - $ {d.subtotal():.2f}\n"
    
    mensaje += f"\n*Subtotal:* $ {subtotal:.2f}\n"
    mensaje += f"*IVA 21%:* $ {iva:.2f}\n"
    mensaje += f"*TOTAL:* $ {total:.2f}\n\n"
    mensaje += f"*Entrega:* Depósito Gráfica Tucán"
    
    mensaje编码 = urllib.parse.quote(mensaje)
    url_whatsapp = f"https://wa.me/{telefono}?text={mensaje编码}"
    
    # Marcar orden como enviada
    from django.utils import timezone
    orden.enviada = True
    orden.fecha_envio = timezone.now()
    orden.save(update_fields=['enviada', 'fecha_envio'])
    
    return JsonResponse({'ok': True, 'url': url_whatsapp})


@login_required
def cambiar_estado_orden(request, pk):
    orden = get_object_or_404(OrdenCompra, pk=pk)
    if request.method == "POST":
        estado_id = request.POST.get("estado")
        try:
            estado = EstadoCompra.objects.get(pk=estado_id)
            orden.estado = estado
            orden.save(update_fields=["estado", "actualizado_en"])
            _registrar_auditoria(request, orden, "update")
            messages.success(request, f"Estado actualizado a {estado.nombre}.")
        except EstadoCompra.DoesNotExist:
            messages.error(request, "Estado invalido.")
    return redirect("detalle_orden_compra", pk=pk)


# ── Remitos ───────────────────────────────────────────────────────────────────

@login_required
def lista_remitos(request):
    remitos = Remito.objects.select_related("proveedor", "usuario", "orden_compra").prefetch_related("detalles__insumo")
    return render(request, "compras/lista_remitos.html", {"remitos": remitos})




def _generar_numero_remito():
    from django.utils import timezone
    from .models import Remito
    anio = timezone.now().year
    prefijo = f"R-{anio}-"
    ultimo = Remito.objects.filter(numero__startswith=prefijo).order_by("-numero").first()
    if ultimo:
        try:
            seq = int(ultimo.numero.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefijo}{seq:04d}"

@login_required
def nuevo_remito(request):
    orden_id = request.GET.get('orden')
    
    # Validar que si hay una OC vinculada, esté confirmada
    if orden_id:
        try:
            orden = OrdenCompra.objects.get(pk=orden_id)
            if orden.estado.nombre.lower() not in ['confirmada', 'aprobada', 'recibida']:
                messages.error(request, f"La orden de compra {orden.pk:04d} debe estar confirmada para registrar un remito.")
                return redirect('compras:nuevo_remito_compra')
        except OrdenCompra.DoesNotExist:
            pass
    
    if request.method == "POST":
        form = RemitoForm(request.POST)
        formset = DetalleRemitoFormSet(request.POST, prefix="detalles")
        if form.is_valid() and formset.is_valid():
            remito = form.save(commit=False)
            remito.usuario = request.user
            remito.save()
            actualizados = []
            for df in formset:
                if df.cleaned_data and not df.cleaned_data.get("DELETE", False):
                    insumo = df.cleaned_data["insumo"]
                    cantidad = df.cleaned_data["cantidad"]
                    precio_unitario = df.cleaned_data.get("precio_unitario") or 0
                    DetalleRemito.objects.create(
                        remito=remito, insumo=insumo,
                        cantidad=cantidad, precio_unitario=precio_unitario,
                    )
                    stock_anterior = insumo.stock or 0
                    insumo.stock = stock_anterior + cantidad
                    insumo.save(update_fields=["stock", "updated_at"])
                    # Registrar MovimientoStock
                    from .models import MovimientoStock
                    MovimientoStock.objects.create(
                        insumo=insumo,
                        tipo="entrada",
                        origen="remito",
                        cantidad=cantidad,
                        stock_anterior=stock_anterior,
                        stock_posterior=insumo.stock,
                        referencia=f"Remito {remito.numero}",
                        remito=remito,
                        fecha=remito.fecha,
                        usuario=request.user if request.user.is_authenticated else None,
                    )
                    actualizados.append(f"{insumo.nombre} (+{cantidad})")
            # Si hay orden de compra vinculada, marcarla como Recibida
            if remito.orden_compra:
                try:
                    estado_recibida = EstadoCompra.objects.get(nombre="Recibida")
                    remito.orden_compra.estado = estado_recibida
                    remito.orden_compra.fecha_recepcion = remito.fecha
                    remito.orden_compra.save(update_fields=["estado", "fecha_recepcion", "actualizado_en"])
                except EstadoCompra.DoesNotExist:
                    pass
            _registrar_auditoria(request, remito, "create")
            messages.success(
                request,
                f"Remito {remito.numero} registrado. Stock actualizado: {', '.join(actualizados)}."
            )
            return redirect('compras:lista_remitos_compra')
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        from datetime import date
        hoy = date.today().strftime("%Y-%m-%d")
        form = RemitoForm(initial={"fecha": hoy, "numero": _generar_numero_remito()})
        formset = DetalleRemitoFormSet(prefix="detalles")
    from insumos.models import Insumo
    return render(request, "compras/nuevo_remito.html", {
        "form": form,
        "formset": formset,
        "insumos": Insumo.objects.filter(activo=True).select_related().order_by("nombre"),
    })


# ── API: items de solicitud de cotizacion confirmada ─────────────────────────
from django.http import JsonResponse

def api_items_solicitud(request, pk):
    """Devuelve los items de una SolicitudCotizacion confirmada en formato JSON."""
    try:
        from automatizacion.models import SolicitudCotizacion
        sc = SolicitudCotizacion.objects.prefetch_related("items__insumo").get(
            pk=pk, estado="confirmada"
        )
        items = []
        # Incluir items con disponible=True o disponible=None (confirmacion sin detalle por item)
        from django.db.models import Q
        for item in sc.items.filter(Q(disponible=True) | Q(disponible__isnull=True)):
            items.append({
                "insumo_id": item.insumo.idInsumo,
                "insumo_nombre": f"{item.insumo.codigo} - {item.insumo.nombre}",
                "cantidad": item.cantidad,
                "precio_unitario": float(item.precio_unitario_respuesta or 0),
            })
        return JsonResponse({"ok": True, "proveedor_id": sc.proveedor_id, "items": items})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=404)


# ── Actualizar precio de insumo ───────────────────────────────────────────────
@login_required
def actualizar_precio_insumo(request, insumo_pk):
    from insumos.models import Insumo
    from django import forms as dj_forms

    insumo = get_object_or_404(Insumo, pk=insumo_pk)

    class PrecioForm(dj_forms.Form):
        precio_unitario = dj_forms.DecimalField(
            min_value=0.01, decimal_places=2,
            widget=dj_forms.NumberInput(attrs={"class": "form-control", "min": "0.01", "step": "0.01"}),
            label="Nuevo Precio Unitario"
        )
        motivo = dj_forms.CharField(
            max_length=200, required=False,
            widget=dj_forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Actualizacion por remito R-0023"}),
            label="Motivo (opcional)"
        )

    if request.method == "POST":
        form = PrecioForm(request.POST)
        if form.is_valid():
            precio_anterior = insumo.precio_unitario
            insumo.precio_unitario = form.cleaned_data["precio_unitario"]
            insumo.save(update_fields=["precio_unitario", "updated_at"])
            _registrar_auditoria(request, insumo, "update")
            messages.success(
                request,
                f"Precio de {insumo.nombre} actualizado: ${precio_anterior} → ${insumo.precio_unitario}."
            )
            return redirect("compras:lista_ordenes_compra")
    else:
        form = PrecioForm(initial={"precio_unitario": insumo.precio_unitario})

    return render(request, "compras/actualizar_precio.html", {
        "form": form,
        "insumo": insumo,
    })


# ── Lista de precios de insumos ───────────────────────────────────────────────
@login_required
def lista_precios_insumos(request):
    from insumos.models import Insumo
    insumos = Insumo.objects.filter(activo=True).select_related("proveedor").order_by("nombre")
    return render(request, "compras/lista_precios.html", {"insumos": insumos})


# ── Home de Compras ───────────────────────────────────────────────────────────
def home_compras(request):
    from .models import OrdenCompra, Remito
    from insumos.models import Insumo
    ordenes_count = OrdenCompra.objects.count()
    remitos_count = Remito.objects.count()
    insumos_count = Insumo.objects.filter(activo=True).count()
    return render(request, "compras/home.html", {
        "ordenes_count": ordenes_count,
        "remitos_count": remitos_count,
        "insumos_count": insumos_count,
    })


# ── Ajuste Masivo de Precios de Insumos ──────────────────────────────────────
@login_required
def ajuste_masivo_precios(request):
    from insumos.models import Insumo
    from django.db.models import Q
    from django.contrib import messages
    from decimal import Decimal
    
    mensaje_resultado = None
    insumos_actualizados = 0
    
    categorias = Insumo.objects.filter(activo=True).values_list('categoria', flat=True).distinct()
    from proveedores.models import Proveedor
    proveedores = Proveedor.objects.filter(activo=True)
    
    ultimos_insumos = Insumo.objects.filter(activo=True).exclude(precio_unitario=0).order_by('-idInsumo')[:10]

    for insumo in ultimos_insumos:
        if insumo.precio_unitario:
            insumo.precio_mas_10 = insumo.precio_unitario * Decimal('1.10')
        else:
            insumo.precio_mas_10 = 0
    
    insumos_count = Insumo.objects.filter(activo=True).count()
    
    if request.method == 'POST':
        porcentaje_str = request.POST.get('porcentaje', '0').replace(',', '.')
        try:
            porcentaje = float(porcentaje_str)
        except ValueError:
            messages.error(request, "Porcentaje inválido. Debe ser un número.")
            porcentaje = None
        
        if porcentaje is not None:
            if porcentaje < -30:
                messages.error(request, "El porcentaje no puede ser menor a -30%")
                porcentaje = None
            elif porcentaje > 100:
                messages.error(request, "El porcentaje no puede ser mayor a 100%")
                porcentaje = None
        
        if porcentaje is None:
            return render(request, "compras/ajuste_masivo_precios.html", {
                'categorias': categorias,
                'proveedores': proveedores,
                'ultimos_insumos': ultimos_insumos,
                'insumos_count': insumos_count,
            })
        
        filtro_categoria = request.POST.get('categoria', '')
        filtro_proveedor = request.POST.get('proveedor', '')
        filtro_tipo = request.POST.get('filtro_tipo', 'todos')
        
        queryset = Insumo.objects.filter(activo=True)
        
        if filtro_categoria:
            queryset = queryset.filter(categoria__icontains=filtro_categoria)
        
        if filtro_proveedor:
            queryset = queryset.filter(proveedor_predeterminado_id=filtro_proveedor)
        
        if filtro_tipo == 'con_precio':
            queryset = queryset.filter(precio_unitario__gt=0)

        from decimal import Decimal
        from django.db import transaction

        factor = Decimal('1') + Decimal(str(porcentaje)) / Decimal('100')

        insumos_actualizados = 0
        errores = []

        with transaction.atomic():
            for insumo in queryset:
                try:
                    if insumo.precio_unitario:
                        nuevo_precio = (insumo.precio_unitario * factor).quantize(Decimal('0.01'))
                        if nuevo_precio < 0:
                            errores.append(f"{insumo.nombre}: precio no puede ser negativo")
                            continue
                        insumo.precio_unitario = nuevo_precio
                        insumo.save(update_fields=['precio_unitario'])
                        insumos_actualizados += 1
                except Exception as e:
                    errores.append(f"{insumo.nombre}: {str(e)}")
        
        if errores:
            messages.warning(request, f"Actualizados {insumos_actualizados} insumos. Errores: {', '.join(errores[:5])}")
        else:
            mensaje_resultado = f"Se actualizaron {insumos_actualizados} insumos con un {'aumento' if porcentaje > 0 else 'descuento'} del {abs(porcentaje)}%"
            messages.success(request, mensaje_resultado)
    
    context = {
        'categorias': categorias,
        'proveedores': proveedores,
        'mensaje_resultado': mensaje_resultado,
        'insumos_actualizados': insumos_actualizados,
        'ultimos_insumos': ultimos_insumos,
        'insumos_count': insumos_count,
    }
    return render(request, "compras/ajuste_masivo_precios.html", context)


@login_required
def api_insumo_sugerencia(request, insumo_pk):
    """Devuelve cantidad_compra_sugerida y precio_unitario de un insumo para pre-llenar OC."""
    from django.http import JsonResponse
    from insumos.models import Insumo
    insumo = get_object_or_404(Insumo, pk=insumo_pk, activo=True)
    return JsonResponse({
        'cantidad_sugerida': insumo.cantidad_compra_sugerida or '',
        'precio_unitario': float(insumo.precio_unitario) if insumo.precio_unitario else '',
    })


# ── Comparacion de precios por proveedor ──────────────────────────────────────
@login_required
def comparacion_precios(request):
    from insumos.models import Insumo
    from proveedores.models import Proveedor
    from django.db.models import Avg, Min, Max, Count

    proveedor_id = request.GET.get("proveedor")
    categoria = request.GET.get("categoria")

    proveedores = Proveedor.objects.filter(activo=True).annotate(
        n_insumos=Count("insumos")
    ).filter(n_insumos__gt=0).order_by("nombre")

    categorias = Insumo.objects.filter(activo=True).values_list(
        "categoria", flat=True
    ).distinct().order_by("categoria")

    qs = Insumo.objects.filter(activo=True).select_related("proveedor").order_by("categoria", "nombre")

    if proveedor_id:
        qs = qs.filter(proveedor_id=proveedor_id)
    if categoria:
        qs = qs.filter(categoria=categoria)

    # Agrupar por categoria
    from collections import defaultdict
    por_categoria = defaultdict(list)
    for insumo in qs:
        por_categoria[insumo.categoria or "Sin categoría"].append(insumo)

    # Estadisticas globales
    stats = Insumo.objects.filter(activo=True).aggregate(
        precio_promedio=Avg("precio_unitario"),
        precio_min=Min("precio_unitario"),
        precio_max=Max("precio_unitario"),
    )

    sin_precio = Insumo.objects.filter(activo=True, precio_unitario=0).count()

    return render(request, "compras/comparacion_precios.html", {
        "por_categoria": dict(por_categoria),
        "proveedores": proveedores,
        "categorias": categorias,
        "proveedor_sel": proveedor_id,
        "categoria_sel": categoria,
        "stats": stats,
        "sin_precio": sin_precio,
        "total": qs.count(),
    })


@login_required
def kardex_insumo(request, insumo_pk):
    from insumos.models import Insumo
    from .models import MovimientoStock
    insumo = get_object_or_404(Insumo, pk=insumo_pk)
    movimientos = MovimientoStock.objects.filter(insumo=insumo).select_related("usuario", "remito").order_by("-fecha", "-creado_en")
    return render(request, "compras/kardex.html", {
        "insumo": insumo,
        "movimientos": movimientos,
    })


@login_required
def ajuste_stock(request, insumo_pk):
    from insumos.models import Insumo
    from .models import MovimientoStock
    from django import forms as dj_forms

    insumo = get_object_or_404(Insumo, pk=insumo_pk)

    class AjusteForm(dj_forms.Form):
        tipo = dj_forms.ChoiceField(
            choices=[("ajuste_positivo", "Ajuste positivo (sumar)"), ("ajuste_negativo", "Ajuste negativo (restar)")],
            widget=dj_forms.Select(attrs={"class": "form-select border border-gray-300 rounded-lg px-3 py-2 text-sm w-full"})
        )
        cantidad = dj_forms.IntegerField(
            min_value=1,
            widget=dj_forms.NumberInput(attrs={"class": "form-control border border-gray-300 rounded-lg px-3 py-2 text-sm w-full", "min": "1"})
        )
        motivo = dj_forms.ChoiceField(
            choices=[("rotura", "Rotura"), ("perdida", "Perdida"), ("error_carga", "Error de carga"), ("otro", "Otro")],
            widget=dj_forms.Select(attrs={"class": "form-select border border-gray-300 rounded-lg px-3 py-2 text-sm w-full"})
        )
        observaciones = dj_forms.CharField(
            required=False,
            widget=dj_forms.Textarea(attrs={"class": "form-control border border-gray-300 rounded-lg px-3 py-2 text-sm w-full", "rows": "2"})
        )

    if request.method == "POST":
        form = AjusteForm(request.POST)
        if form.is_valid():
            tipo = form.cleaned_data["tipo"]
            cantidad = form.cleaned_data["cantidad"]
            motivo = form.cleaned_data["motivo"]
            obs = form.cleaned_data["observaciones"]
            stock_anterior = insumo.stock or 0
            if tipo == "ajuste_positivo":
                insumo.stock = stock_anterior + cantidad
            else:
                insumo.stock = max(0, stock_anterior - cantidad)
            insumo.save(update_fields=["stock", "updated_at"])
            MovimientoStock.objects.create(
                insumo=insumo,
                tipo=tipo,
                origen="ajuste",
                cantidad=cantidad,
                stock_anterior=stock_anterior,
                stock_posterior=insumo.stock,
                referencia=f"Ajuste: {motivo}",
                observaciones=obs,
                fecha=__import__("django.utils.timezone", fromlist=["timezone"]).timezone.now().date(),
                usuario=request.user if request.user.is_authenticated else None,
            )
            _registrar_auditoria(request, insumo, "update")
            messages.success(request, f"Ajuste aplicado: {insumo.nombre} stock {stock_anterior} → {insumo.stock}.")
            return redirect("compras:kardex_insumo", insumo_pk=insumo.pk)
    else:
        form = AjusteForm()

    return render(request, "compras/ajuste_stock.html", {"form": form, "insumo": insumo})


@login_required
def api_items_orden(request, pk):
    from .models import OrdenCompra
    try:
        oc = OrdenCompra.objects.prefetch_related("detalles__insumo").get(pk=pk)
        items = []
        for d in oc.detalles.all():
            items.append({
                "insumo_id": d.insumo.idInsumo,
                "insumo_nombre": d.insumo.nombre,
                "insumo_codigo": d.insumo.codigo,
                "cantidad": d.cantidad,
                "unidad": d.insumo.unidad_medida or "-",
            })
        from django.http import JsonResponse
        return JsonResponse({"ok": True, "proveedor_id": oc.proveedor_id, "items": items})
    except Exception as e:
        from django.http import JsonResponse
        return JsonResponse({"ok": False, "error": str(e)}, status=404)


@login_required
def orden_pdf(request, pk):
    from django.http import HttpResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    
    orden = get_object_or_404(OrdenCompra.objects.select_related("proveedor").prefetch_related("detalles__insumo"), pk=pk)
    
    if orden.monto_total == 0:
        total = sum(d.subtotal() for d in orden.detalles.all())
        if total > 0:
            orden.monto_total = total
            orden.save(update_fields=["monto_total"])
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="OC-{orden.pk:04d}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título
    elements.append(Paragraph(f"ORDEN DE COMPRA", styles['Title']))
    elements.append(Spacer(1, 0.5*cm))
    
    # Datos de la orden
    condicion_pago_text = dict(OrdenCompra.CONDICIONES_PAGO).get(orden.condicion_pago, 'Contado')
    data = [
        ["Orden:", f"OC-{orden.pk:04d}"],
        ["Fecha:", orden.fecha_creacion.strftime('%d/%m/%Y')],
        ["Condición de pago:", condicion_pago_text],
        ["Fecha entrega:", orden.fecha_entrega.strftime('%d/%m/%Y') if orden.fecha_entrega else 'A convenir'],
    ]
    
    t = Table(data, colWidths=[5*cm, 10*cm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.5*cm))
    
    # Proveedor
    elements.append(Paragraph("<b>Proveedor:</b>", styles['Normal']))
    elements.append(Paragraph(f"{orden.proveedor.nombre}", styles['Normal']))
    elements.append(Paragraph(f"CUIT: {orden.proveedor.cuit or '-'}", styles['Normal']))
    elements.append(Paragraph(f"{orden.proveedor.direccion or '-'}", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))
    
    # Detalles
    elements.append(Paragraph("<b>Detalle:</b>", styles['Normal']))
    data = [["#", "Código", "Descripción", "Cant.", "Unidad", "P. Unit.", "Subtotal"]]
    num = 1
    for d in orden.detalles.all():
        codigo = getattr(d.insumo, 'codigo', None) or f"IN-{d.insumo.pk:03d}"
        unidad = getattr(d.insumo, 'unidad_medida', None) or 'un'
        data.append([
            str(num),
            codigo,
            d.insumo.nombre[:30],
            str(d.cantidad),
            unidad,
            f"$ {d.precio_unitario}",
            f"$ {d.subtotal()}"
        ])
        num += 1
    
    # Totales
    subtotal = float(orden.monto_total)
    iva = subtotal * 0.21
    total = subtotal + iva
    
    data.append(["", "", "", "", "Subtotal", f"$ {subtotal:.2f}"])
    data.append(["", "", "", "", "IVA 21%", f"$ {iva:.2f}"])
    data.append(["", "", "", "", "<b>Total</b>", f"<b>$ {total:.2f}</b>"])
    
    t = Table(data, colWidths=[1*cm, 2*cm, 5*cm, 1.5*cm, 2*cm, 2.5*cm, 2.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -2), 1, colors.black),
        ('ALIGN', (3, 0), (3, -1), 'CENTER'),
        ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
    ]))
    elements.append(t)
    
    # Observaciones
    if orden.observaciones:
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph("<b>Observaciones:</b>", styles['Normal']))
        elements.append(Paragraph(orden.observaciones, styles['Normal']))
    
    doc.build(elements)
    return response


@login_required
def exportar_ordenes_excel(request):
    import csv
    from django.http import HttpResponse
    
    ids = request.GET.get('ids', '').split(',')
    if not ids or ids == ['']:
        ordenes = OrdenCompra.objects.select_related('proveedor', 'estado').all()
    else:
        ordenes = OrdenCompra.objects.select_related('proveedor', 'estado').filter(pk__in=ids)
    
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="ordenes_compra.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Nº Orden', 'Proveedor', 'CUIT Proveedor', 'Condición Pago', 'Estado', 'Enviada', 'Fecha Creación', 'Fecha Entrega', 'Fecha Recepción', 'Total', 'Usuario', 'Observaciones'])
    
    for orden in ordenes:
        writer.writerow([
            f'OC-{orden.pk:04d}',
            orden.proveedor.nombre,
            orden.proveedor.cuit or '',
            orden.get_condicion_pago_display(),
            orden.estado.nombre,
            'Sí' if orden.enviada else 'No',
            orden.fecha_creacion.strftime('%d/%m/%Y'),
            orden.fecha_entrega.strftime('%d/%m/%Y') if orden.fecha_entrega else '',
            orden.fecha_recepcion.strftime('%d/%m/%Y') if orden.fecha_recepcion else '',
            str(orden.monto_total),
            orden.usuario.get_full_name() if orden.usuario else '',
            orden.observaciones or '',
        ])
    
    return response
