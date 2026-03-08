from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Presupuesto, PresupuestoDetalle
from .forms import PresupuestoForm
from .formsets import PresupuestoDetalleFormSet
from .utils import _fmt_ars
from configuracion.permissions import require_perm


def index(request):
    return redirect('lista_presupuestos')


@require_perm('Presupuestos', 'Listar')
def lista_presupuestos(request):
    query = request.GET.get('q', '') or request.GET.get('criterio', '')
    order_by = request.GET.get('order_by', 'fecha')
    direction = request.GET.get('direction', 'desc')
    fecha = request.GET.get('fecha')

    valid_order_fields = ['id', 'numero', 'cliente__apellido', 'cliente__nombre', 'fecha', 'validez', 'total', 'estado']
    if order_by not in valid_order_fields:
        order_by = 'fecha'

    qs = Presupuesto.objects.select_related('cliente').all()
    if query:
        qs = qs.filter(
            Q(numero__icontains=query) |
            Q(cliente__nombre__icontains=query) |
            Q(cliente__apellido__icontains=query) |
            Q(cliente__razon_social__icontains=query) |
            Q(estado__icontains=query)
        )

    # Filtro por fecha exacta (día específico)
    if fecha:
        qs = qs.filter(fecha=fecha)

    order_field = f'-{order_by}' if direction == 'desc' else order_by
    qs = qs.order_by(order_field)

    from configuracion.services import get_page_size
    paginator = Paginator(qs, get_page_size())
    page = request.GET.get('page')
    presupuestos = paginator.get_page(page)

    nuevo_pk = request.GET.get('nuevo')
    nuevo_presupuesto = None
    if nuevo_pk:
        try:
            nuevo_presupuesto = Presupuesto.objects.select_related('cliente').get(pk=int(nuevo_pk))
        except (Presupuesto.DoesNotExist, ValueError):
            pass

    return render(request, 'presupuestos/lista_presupuestos.html', {
        'presupuestos': presupuestos,
        'query': query,
        'order_by': order_by,
        'direction': direction,
        'fecha': fecha,
        'nuevo_presupuesto': nuevo_presupuesto,
    })


@require_perm('Presupuestos', 'Crear')
def crear_presupuesto(request):
    from decimal import Decimal
    from datetime import date, timedelta
    from productos.models import Producto as ProductoModel
    from clientes.models import Cliente as ClienteModel

    productos_lista = list(ProductoModel.objects.filter(activo=True).values('pk', 'nombreProducto', 'precioUnitario'))
    clientes_data = list(ClienteModel.objects.values(
        'pk', 'nombre', 'apellido', 'razon_social', 'cuit',
        'direccion', 'ciudad', 'provincia', 'pais',
        'telefono', 'celular', 'email', 'tipo_cliente',
    ))
    today = date.today()
    validez_default = (today + timedelta(days=30)).strftime('%Y-%m-%d')

    if request.method == 'POST':
        form = PresupuestoForm(request.POST)
        if form.is_valid():
            presupuesto = form.save(commit=False)
            # Generar número automático
            ultimo = Presupuesto.objects.order_by('-id').first()
            if ultimo and ultimo.numero and ultimo.numero.startswith('P-'):
                try:
                    last_num = int(ultimo.numero.split('-')[1])
                except Exception:
                    last_num = ultimo.id
            else:
                last_num = ultimo.id if ultimo else 0
            presupuesto.numero = f"P-{last_num + 1:05d}"
            presupuesto.save()

            # Leer descuento/IVA global
            descuento_global = request.POST.get('descuento_global', '0').strip()
            iva_aplicada_val = request.POST.get('iva_aplicada', '0').strip()
            descuento_pct = Decimal(descuento_global or '0')
            iva_pct = Decimal(iva_aplicada_val or '0')

            # Reconstruir detalles desde det-{i}-*
            total = Decimal('0')
            indices = set()
            for key in request.POST:
                if key.startswith('det-') and key.endswith('-producto'):
                    indices.add(key.split('-')[1])
            for idx in indices:
                prod_pk = request.POST.get(f'det-{idx}-producto', '').strip()
                cantidad_raw = request.POST.get(f'det-{idx}-cantidad', '').strip()
                precio_raw = request.POST.get(f'det-{idx}-precio_unitario', '').strip()
                if not prod_pk or not cantidad_raw or not precio_raw:
                    continue
                try:
                    prod = ProductoModel.objects.get(pk=int(prod_pk))
                    cantidad = int(cantidad_raw)
                    precio = Decimal(precio_raw)
                    neto = cantidad * precio
                    con_descuento = neto * (1 - descuento_pct / Decimal('100'))
                    subtotal = con_descuento * (1 + iva_pct / Decimal('100'))
                    PresupuestoDetalle.objects.create(
                        presupuesto=presupuesto,
                        producto=prod,
                        cantidad=cantidad,
                        precio_unitario=precio,
                        descuento=descuento_pct,
                        iva=iva_pct,
                        subtotal=subtotal,
                    )
                    total += subtotal
                except Exception:
                    continue
            presupuesto.total = total
            presupuesto.save()
            return redirect(f"/presupuestos/lista/?nuevo={presupuesto.pk}")
    else:
        form = PresupuestoForm()

    return render(request, 'presupuestos/crear_presupuesto.html', {
        'form': form,
        'productos_lista': productos_lista,
        'clientes_data': clientes_data,
        'validez_default': validez_default,
    })


@require_perm('Presupuestos', 'Editar')
def editar_presupuesto(request, pk):
    from decimal import Decimal
    from datetime import date, timedelta
    from productos.models import Producto as ProductoModel
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    detalles_qs = presupuesto.detalles.select_related('producto').all()
    productos_lista = list(ProductoModel.objects.filter(activo=True).values('pk', 'nombreProducto', 'precioUnitario'))

    if request.method == 'POST':
        form = PresupuestoForm(request.POST, instance=presupuesto)
        if form.is_valid():
            presupuesto = form.save(commit=False)
            # Reconstruir detalles desde los campos ocultos enviados
            presupuesto.save()
            presupuesto.detalles.all().delete()
            total = Decimal('0')
            indices = set()
            for key in request.POST:
                if key.startswith('det-') and key.endswith('-producto'):
                    indices.add(key.split('-')[1])
            descuento_global = request.POST.get('descuento_global', '0').strip()
            iva_aplicada_val = request.POST.get('iva_aplicada', '0').strip()
            descuento_pct = Decimal(descuento_global or '0')
            iva_pct = Decimal(iva_aplicada_val or '0')
            for idx in indices:
                prod_pk = request.POST.get(f'det-{idx}-producto', '').strip()
                cantidad_raw = request.POST.get(f'det-{idx}-cantidad', '').strip()
                precio_raw = request.POST.get(f'det-{idx}-precio_unitario', '').strip()
                if not prod_pk or not cantidad_raw or not precio_raw:
                    continue
                try:
                    prod = ProductoModel.objects.get(pk=int(prod_pk))
                    cantidad = int(cantidad_raw)
                    precio = Decimal(precio_raw)
                    neto = cantidad * precio
                    con_descuento = neto * (1 - descuento_pct / Decimal('100'))
                    subtotal = con_descuento * (1 + iva_pct / Decimal('100'))
                    PresupuestoDetalle.objects.create(
                        presupuesto=presupuesto,
                        producto=prod,
                        cantidad=cantidad,
                        precio_unitario=precio,
                        descuento=descuento_pct,
                        iva=iva_pct,
                        subtotal=subtotal,
                    )
                    total += subtotal
                except Exception:
                    continue
            presupuesto.total = total
            presupuesto.save()
            return redirect('presupuestos:lista')
    else:
        form = PresupuestoForm(instance=presupuesto)

    today = date.today()
    validez_default = (presupuesto.validez if presupuesto.validez and presupuesto.validez >= today else today + timedelta(days=30)).strftime('%Y-%m-%d')

    from clientes.models import Cliente as ClienteModel
    clientes_data = list(ClienteModel.objects.values(
        'pk', 'nombre', 'apellido', 'razon_social', 'cuit',
        'direccion', 'ciudad', 'provincia', 'pais',
        'telefono', 'celular', 'email', 'tipo_cliente',
    ))

    primer_det = detalles_qs.first()
    global_descuento = int(primer_det.descuento) if primer_det else 0
    global_iva_aplicada = (primer_det.iva > 0) if primer_det else True

    return render(request, 'presupuestos/editar_presupuesto.html', {
        'form': form,
        'presupuesto': presupuesto,
        'detalles': detalles_qs,
        'productos_lista': productos_lista,
        'validez_default': validez_default,
        'clientes_data': clientes_data,
        'global_descuento': global_descuento,
        'global_iva_aplicada': global_iva_aplicada,
    })


@require_perm('Presupuestos', 'Eliminar')
def eliminar_presupuesto(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    if request.method == 'POST':
        presupuesto.delete()
        return redirect('presupuestos:lista')
    return render(request, 'presupuestos/eliminar_presupuesto.html', {'presupuesto': presupuesto})


@require_perm('Presupuestos', 'Listar')
def enviar_presupuesto(request, pk):
    import urllib.parse
    from django.conf import settings
    from django.http import JsonResponse

    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    cliente = presupuesto.cliente
    link = request.build_absolute_uri(f'/presupuestos/respuesta/{presupuesto.token}/')
    metodo = request.POST.get('metodo', '').strip()

    if metodo == 'email':
        if not cliente.email:
            return JsonResponse({'error': 'El cliente no tiene email registrado'}, status=400)
        asunto = f'Presupuesto {presupuesto.numero} – Imprenta Tucán'
        texto_plano = f'Ver presupuesto: {link}'
        html_body = (
            f'<p>Estimado/a <strong>{cliente.nombre} {cliente.apellido}</strong>,</p>'
            f'<p>Le enviamos el presupuesto <strong>{presupuesto.numero}</strong> '
            f'por un total de <strong>${presupuesto.total}</strong>.</p>'
            f'<p>Válido hasta: {presupuesto.validez or "Sin fecha límite"}.</p>'
            f'<p><a href="{link}" style="background:#2563eb;color:#fff;padding:10px 20px;'
            f'border-radius:6px;text-decoration:none;display:inline-block;">'
            f'Ver y responder presupuesto</a></p>'
            f'<p>Imprenta Tucán</p>'
        )
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@imprenta.local')
        try:
            from django.core.mail import EmailMultiAlternatives
            from .utils import generar_pdf_presupuesto
            msg = EmailMultiAlternatives(asunto, texto_plano, from_email, [cliente.email])
            msg.attach_alternative(html_body, 'text/html')
            pdf_bytes = generar_pdf_presupuesto(presupuesto, link)
            if pdf_bytes:
                msg.attach(
                    f'presupuesto_{presupuesto.numero}.pdf',
                    pdf_bytes,
                    'application/pdf',
                )
            msg.send(fail_silently=False)
            return JsonResponse({'status': 'ok', 'mensaje': f'Email enviado a {cliente.email}'})
        except Exception as e:
            return JsonResponse({'error': f'Error al enviar: {e}'}, status=500)

    elif metodo == 'whatsapp':
        numero = (cliente.celular or cliente.telefono or '').strip()
        numero_digits = ''.join(c for c in numero if c.isdigit())
        if not numero_digits:
            return JsonResponse({'error': 'El cliente no tiene celular/teléfono registrado'}, status=400)
        nombre_cliente = f'{cliente.nombre} {cliente.apellido}'
        pdf_link   = request.build_absolute_uri(f'/presupuestos/pdf/{presupuesto.token}/')
        link_aceptar  = request.build_absolute_uri(f'/presupuestos/ok/{presupuesto.token}/aceptado/')
        link_rechazar = request.build_absolute_uri(f'/presupuestos/ok/{presupuesto.token}/rechazado/')
        validez_str = presupuesto.validez.strftime('%d/%m/%Y') if presupuesto.validez else None
        validez_texto = f'Válido hasta: {validez_str}.\n' if validez_str else ''
        texto = (
            f'Hola {nombre_cliente}! Le enviamos el presupuesto '
            f'{presupuesto.numero} de Imprenta Tucán por un total de {_fmt_ars(presupuesto.total)}.\n'
            f'{validez_texto}\n'
            f'✅ *ACEPTAR presupuesto* (un clic):\n{link_aceptar}\n\n'
            f'❌ *RECHAZAR presupuesto* (un clic):\n{link_rechazar}\n\n'
            f'📄 Ver detalle completo / PDF:\n{pdf_link}'
        )
        wa_url = f'https://wa.me/{numero_digits}?text={urllib.parse.quote(texto)}'
        return JsonResponse({'status': 'ok', 'url': wa_url, 'texto': texto})

    elif metodo == 'sms':
        numero = (cliente.celular or cliente.telefono or '').strip()
        if not numero:
            return JsonResponse({'error': 'El cliente no tiene celular/teléfono registrado'}, status=400)
        texto = (
            f'Presupuesto {presupuesto.numero} de Imprenta Tucán '
            f'por ${presupuesto.total}. Responder: {link}'
        )
        sms_url = f'sms:{numero}?body={urllib.parse.quote(texto)}'
        return JsonResponse({'status': 'ok', 'url': sms_url})

    return JsonResponse({'error': 'Método de envío inválido'}, status=400)


def respuesta_cliente_view(request, token):
    presupuesto = get_object_or_404(Presupuesto, token=token)
    detalles = presupuesto.detalles.select_related('producto').all()
    return render(request, 'presupuestos/respuesta_cliente.html', {
        'presupuesto': presupuesto,
        'detalles': detalles,
    })


def procesar_respuesta(request, token, accion):
    from django.http import HttpResponseBadRequest
    presupuesto = get_object_or_404(Presupuesto, token=token)
    detalles = presupuesto.detalles.select_related('producto').all()

    if presupuesto.respuesta_cliente != 'pendiente':
        return render(request, 'presupuestos/respuesta_cliente.html', {
            'presupuesto': presupuesto,
            'detalles': detalles,
            'ya_respondido': True,
        })

    if request.method == 'POST' and accion in ('aceptado', 'rechazado'):
        presupuesto.respuesta_cliente = accion
        presupuesto.save()
        return render(request, 'presupuestos/respuesta_cliente.html', {
            'presupuesto': presupuesto,
            'detalles': detalles,
            'respuesta_registrada': True,
        })

    return HttpResponseBadRequest('Acción inválida')


def accion_directa(request, token, accion):
    """Acepta o rechaza un presupuesto via GET (enlace directo desde WhatsApp/email)."""
    presupuesto = get_object_or_404(Presupuesto, token=token)
    detalles = presupuesto.detalles.select_related('producto').all()

    if accion not in ('aceptado', 'rechazado'):
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest('Acción inválida')

    if presupuesto.respuesta_cliente != 'pendiente':
        return render(request, 'presupuestos/respuesta_cliente.html', {
            'presupuesto': presupuesto,
            'detalles': detalles,
            'ya_respondido': True,
        })

    presupuesto.respuesta_cliente = accion
    presupuesto.save()
    return render(request, 'presupuestos/respuesta_cliente.html', {
        'presupuesto': presupuesto,
        'detalles': detalles,
        'respuesta_registrada': True,
    })


def descargar_pdf_presupuesto(request, token):
    """Vista pública (acceso por token) para descargar el PDF de un presupuesto."""
    from django.http import HttpResponse
    from .utils import generar_pdf_presupuesto
    presupuesto = get_object_or_404(Presupuesto, token=token)
    link = request.build_absolute_uri(f'/presupuestos/respuesta/{presupuesto.token}/')
    pdf_bytes = generar_pdf_presupuesto(presupuesto, link)
    if pdf_bytes is None:
        return HttpResponse('PDF no disponible (reportlab no instalado)', status=503)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="presupuesto_{presupuesto.numero}.pdf"'
    )
    return response


def imagen_presupuesto(request, token):
    """Vista pública: devuelve el presupuesto como imagen PNG (og:image / WhatsApp preview)."""
    from django.http import HttpResponse
    from .utils import generar_imagen_presupuesto
    presupuesto = get_object_or_404(Presupuesto, token=token)
    png_bytes = generar_imagen_presupuesto(presupuesto)
    if png_bytes is None:
        return HttpResponse('Imagen no disponible', status=503)
    response = HttpResponse(png_bytes, content_type='image/png')
    response['Cache-Control'] = 'public, max-age=3600'
    return response
