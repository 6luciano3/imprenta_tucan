"""Vistas para Órdenes de Pago — se importan desde views.py via include."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.http import JsonResponse
from decimal import Decimal, InvalidOperation

from .models import (
    OrdenCompra, OrdenPago, ComprobanteOrdenPago,
    FormaPagoOrdenPago, RetencionOrdenPago,
)
from configuracion.permissions import require_perm


def _registrar_auditoria(request, op, estado_anterior, estado_nuevo):
    """Registra un AuditEntry cada vez que cambia el estado de una OrdenPago."""
    try:
        from auditoria.models import AuditEntry
        import json
        AuditEntry.objects.create(
            user=request.user,
            ip_address=request.META.get('REMOTE_ADDR'),
            path=request.path,
            method=request.method,
            app_label='compras',
            model='OrdenPago',
            object_id=str(op.pk),
            object_repr=str(op),
            action='update',
            changes=json.dumps({'estado': [estado_anterior, estado_nuevo]}),
        )
    except Exception:
        pass  # La auditoría nunca debe romper el flujo principal


def _datos_empresa():
    try:
        from configuracion.models import Parametro
        return {
            'nombre':    Parametro.get('EMPRESA_NOMBRE',       'Imprenta Tucán S.A.'),
            'cuit':      Parametro.get('EMPRESA_CUIT',         ''),
            'domicilio': Parametro.get('EMPRESA_DOMICILIO',    ''),
            'telefono':  Parametro.get('EMPRESA_TELEFONO',     ''),
            'email':     Parametro.get('EMPRESA_EMAIL',        ''),
            'iva':       Parametro.get('EMPRESA_CONDICION_IVA','Responsable Inscripto'),
        }
    except Exception:
        return {'nombre': 'Imprenta Tucán S.A.', 'cuit': '', 'domicilio': '', 'telefono': '', 'email': '', 'iva': 'Responsable Inscripto'}


def _to_dec(v):
    try:
        return Decimal(str(v).replace(',', '.'))
    except (InvalidOperation, TypeError):
        return Decimal('0')


@login_required
def lista_ordenes_pago(request):
    from django.core.paginator import Paginator
    from django.db.models import Q
    from proveedores.models import Proveedor

    qs = OrdenPago.objects.select_related('proveedor', 'orden_compra', 'usuario').order_by('-creado_en')

    q           = request.GET.get('q', '').strip()
    estado      = request.GET.get('estado', '')
    proveedor_id = request.GET.get('proveedor', '')

    if q:
        qs = qs.filter(Q(numero__icontains=q) | Q(proveedor__nombre__icontains=q))
    if estado:
        qs = qs.filter(estado=estado)
    if proveedor_id:
        qs = qs.filter(proveedor_id=proveedor_id)

    paginator = Paginator(qs, 15)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'compras/lista_ordenes_pago.html', {
        'page_obj':        page_obj,
        'ordenes':         page_obj,
        'q':               q,
        'estado_sel':      estado,
        'proveedor_sel':   proveedor_id,
        'estados':         OrdenPago.ESTADOS,
        'proveedores':     Proveedor.objects.filter(activo=True).order_by('nombre'),
        'total_pendientes': OrdenPago.objects.filter(estado='pendiente').count(),
        'total_aprobadas':  OrdenPago.objects.filter(estado='aprobada').count(),
        'total_pagadas':    OrdenPago.objects.filter(estado='pagada').count(),
    })


@login_required
def nueva_orden_pago(request):
    from proveedores.models import Proveedor

    proveedores   = Proveedor.objects.filter(activo=True).order_by('nombre')
    ordenes_compra = OrdenCompra.objects.select_related('proveedor', 'estado').order_by('-creado_en')

    if request.method == 'POST':
        proveedor_id  = request.POST.get('proveedor')
        oc_id         = request.POST.get('orden_compra') or None
        moneda        = request.POST.get('moneda', 'ARS')
        vencimiento   = request.POST.get('fecha_vencimiento') or None
        observaciones = request.POST.get('observaciones', '')

        comp_tipos    = request.POST.getlist('comp_tipo')
        comp_numeros  = request.POST.getlist('comp_numero')
        comp_fechas   = request.POST.getlist('comp_fecha')
        comp_importes = request.POST.getlist('comp_importe')
        comp_saldos   = request.POST.getlist('comp_saldo')

        fp_metodos  = request.POST.getlist('fp_metodo')
        fp_bancos   = request.POST.getlist('fp_banco')
        fp_cbus     = request.POST.getlist('fp_cbu')
        fp_cheques  = request.POST.getlist('fp_cheque')
        fp_refs     = request.POST.getlist('fp_referencia')
        fp_importes = request.POST.getlist('fp_importe')

        ret_tipos    = request.POST.getlist('ret_tipo')
        ret_descs    = request.POST.getlist('ret_descripcion')
        ret_importes = request.POST.getlist('ret_importe')

        if not proveedor_id:
            messages.error(request, 'Seleccioná un proveedor.')
        elif not any(n.strip() for n in comp_numeros):
            messages.error(request, 'Agregá al menos un comprobante.')
        else:
            # G — Validar comprobantes duplicados para este proveedor
            comp_duplicado = None
            for i, tipo in enumerate(comp_tipos):
                num_check = comp_numeros[i].strip() if i < len(comp_numeros) else ''
                if num_check:
                    existente = ComprobanteOrdenPago.objects.filter(
                        orden_pago__proveedor_id=proveedor_id,
                        tipo=tipo,
                        numero=num_check,
                    ).exclude(orden_pago__estado='anulada').select_related('orden_pago').first()
                    if existente:
                        comp_duplicado = (tipo.replace('_', ' ').title(), num_check, existente.orden_pago.numero)
                        break

            if comp_duplicado:
                tipo_d, num_d, op_num = comp_duplicado
                messages.error(
                    request,
                    f'El comprobante {tipo_d} N° {num_d} ya está registrado '
                    f'en la OP-{op_num}. Verificá antes de continuar.'
                )
            else:
                op = OrdenPago.objects.create(
                    proveedor_id=proveedor_id,
                    orden_compra_id=oc_id,
                    moneda=moneda,
                    fecha_vencimiento=vencimiento or None,
                    observaciones=observaciones,
                    usuario=request.user,
                    estado='pendiente',
                )

                for i, tipo in enumerate(comp_tipos):
                    numero  = comp_numeros[i]  if i < len(comp_numeros)  else ''
                    fecha   = comp_fechas[i]   if i < len(comp_fechas)   else None
                    importe = _to_dec(comp_importes[i]) if i < len(comp_importes) else Decimal('0')
                    saldo   = _to_dec(comp_saldos[i])   if i < len(comp_saldos)   else Decimal('0')
                    if numero.strip():
                        ComprobanteOrdenPago.objects.create(
                            orden_pago=op, tipo=tipo, numero=numero,
                            fecha=fecha or timezone.now().date(),
                            importe=importe, saldo_pendiente=saldo,
                        )

                for i, metodo in enumerate(fp_metodos):
                    imp = _to_dec(fp_importes[i]) if i < len(fp_importes) else Decimal('0')
                    FormaPagoOrdenPago.objects.create(
                        orden_pago=op, metodo=metodo,
                        banco=fp_bancos[i]  if i < len(fp_bancos)  else '',
                        cbu=fp_cbus[i]      if i < len(fp_cbus)    else '',
                        numero_cheque=fp_cheques[i] if i < len(fp_cheques) else '',
                        referencia=fp_refs[i]       if i < len(fp_refs)    else '',
                        importe=imp,
                    )

                for i, tipo in enumerate(ret_tipos):
                    imp = _to_dec(ret_importes[i]) if i < len(ret_importes) else Decimal('0')
                    RetencionOrdenPago.objects.create(
                        orden_pago=op, tipo=tipo,
                        descripcion=ret_descs[i] if i < len(ret_descs) else '',
                        importe=imp,
                    )

                op.recalcular_totales()

                # H — Alertar si el monto supera >10% el total de la OC asociada
                if oc_id:
                    try:
                        oc = OrdenCompra.objects.get(pk=oc_id)
                        if oc.monto_total > 0 and op.monto_total > oc.monto_total * Decimal('1.10'):
                            messages.warning(
                                request,
                                f'Atención: el monto de esta OP (${op.monto_total:.2f}) supera en más '
                                f'del 10% el total de la OC-{oc.pk:04d} (${oc.monto_total:.2f}). '
                                f'Verificá si hay diferencias en precios o cantidades.'
                            )
                    except OrdenCompra.DoesNotExist:
                        pass

                messages.success(request, f'Orden de Pago N° {op.numero} creada correctamente.')
                return redirect('compras:lista_ordenes_pago')

    return render(request, 'compras/nueva_orden_pago.html', {
        'proveedores':       proveedores,
        'ordenes_compra':    ordenes_compra,
        'monedas':           OrdenPago.MONEDAS,
        'tipos_comprobante': ComprobanteOrdenPago.TIPOS,
        'metodos_pago':      FormaPagoOrdenPago.METODOS,
        'tipos_retencion':   RetencionOrdenPago.TIPOS,
        'hoy':               timezone.now().date().isoformat(),
    })


@login_required
def detalle_orden_pago_json(request, pk):
    op = get_object_or_404(
        OrdenPago.objects
            .select_related('proveedor', 'orden_compra', 'usuario', 'usuario_aprobacion')
            .prefetch_related('comprobantes', 'formas_pago', 'retenciones'),
        pk=pk,
    )
    prov = op.proveedor
    empresa = _datos_empresa()

    return JsonResponse({
        'empresa':     empresa,
        'numero':      op.numero,
        'fecha':       op.creado_en.strftime('%d/%m/%Y'),
        'estado':      op.get_estado_display(),
        'estado_key':  op.estado,
        'usuario':     str(op.usuario) if op.usuario else '',
        'moneda':      op.moneda,
        'observaciones': op.observaciones,
        'fecha_vencimiento': op.fecha_vencimiento.strftime('%d/%m/%Y') if op.fecha_vencimiento else '',
        'fecha_pago':  op.fecha_pago.strftime('%d/%m/%Y') if op.fecha_pago else '',
        'proveedor': {
            'nombre':        prov.nombre,
            'cuit':          getattr(prov, 'cuit', '') or '',
            'condicion_iva': getattr(prov, 'condicion_iva', '') or 'Responsable Inscripto',
            'direccion':     getattr(prov, 'direccion', '') or '',
            'email':         getattr(prov, 'email', '') or '',
        },
        'comprobantes': [
            {
                'tipo':           c.get_tipo_display(),
                'numero':         c.numero,
                'fecha':          c.fecha.strftime('%d/%m/%Y'),
                'importe':        float(c.importe),
                'saldo_pendiente': float(c.saldo_pendiente),
            }
            for c in op.comprobantes.all()
        ],
        'formas_pago': [
            {
                'metodo':         fp.get_metodo_display(),
                'banco':          fp.banco,
                'cbu':            fp.cbu,
                'numero_cheque':  fp.numero_cheque,
                'referencia':     fp.referencia,
                'importe':        float(fp.importe),
            }
            for fp in op.formas_pago.all()
        ],
        'retenciones': [
            {
                'tipo':        r.get_tipo_display(),
                'descripcion': r.descripcion,
                'importe':     float(r.importe),
            }
            for r in op.retenciones.all()
        ],
        'monto_total':       float(op.monto_total),
        'monto_retenciones': float(op.monto_retenciones),
        'monto_neto':        float(op.monto_neto),
    })


@require_POST
@login_required
@require_perm('Compras', 'Editar')
def aprobar_orden_pago(request, pk):
    op = get_object_or_404(OrdenPago, pk=pk)
    if op.estado == 'pendiente':
        estado_anterior = op.estado
        op.estado = 'aprobada'
        op.usuario_aprobacion = request.user
        op.save(update_fields=['estado', 'usuario_aprobacion', 'actualizado_en'])
        _registrar_auditoria(request, op, estado_anterior, 'aprobada')
        messages.success(request, f'Orden de Pago N° {op.numero} aprobada.')
    else:
        messages.warning(request, 'Solo se pueden aprobar órdenes en estado Pendiente.')
    return redirect('compras:lista_ordenes_pago')


@require_POST
@login_required
@require_perm('Compras', 'Editar')
def registrar_pago(request, pk):
    from datetime import date
    op = get_object_or_404(OrdenPago, pk=pk)
    # S-6: solo se puede pagar una orden que fue previamente aprobada.
    # El estado 'pendiente' requiere pasar por aprobación primero.
    if op.estado == 'aprobada':
        estado_anterior = op.estado
        op.estado = 'pagada'
        fecha_pago = request.POST.get('fecha_pago')
        op.fecha_pago = fecha_pago if fecha_pago else date.today()
        op.save(update_fields=['estado', 'fecha_pago', 'actualizado_en'])
        _registrar_auditoria(request, op, estado_anterior, 'pagada')
        messages.success(request, f'Orden de Pago N° {op.numero} marcada como pagada.')
    else:
        messages.warning(request, 'Esta orden no puede marcarse como pagada.')
    return redirect('compras:lista_ordenes_pago')


@login_required
@require_perm('Compras', 'Ver')
def exportar_ordenes_pago_excel(request):
    import csv
    from django.http import HttpResponse
    from django.db.models import Q

    qs = OrdenPago.objects.select_related('proveedor', 'orden_compra', 'usuario').order_by('-creado_en')

    # Filtros opcionales (reutiliza los mismos params de lista)
    estado = request.GET.get('estado', '')
    proveedor_id = request.GET.get('proveedor', '')
    q = request.GET.get('q', '').strip()
    if estado:
        qs = qs.filter(estado=estado)
    if proveedor_id:
        qs = qs.filter(proveedor_id=proveedor_id)
    if q:
        qs = qs.filter(Q(numero__icontains=q) | Q(proveedor__nombre__icontains=q))

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="ordenes_pago.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'N° Orden', 'Proveedor', 'CUIT', 'OC Asociada', 'Moneda',
        'Estado', 'Total', 'Retenciones', 'Neto a Pagar',
        'Fecha Creación', 'Fecha Vencimiento', 'Fecha Pago',
        'Creado por', 'Aprobado por', 'Observaciones',
    ])
    for op in qs:
        writer.writerow([
            f'OP-{op.numero}',
            op.proveedor.nombre,
            getattr(op.proveedor, 'cuit', '') or '',
            f'OC-{op.orden_compra.pk:04d}' if op.orden_compra else '',
            op.moneda,
            op.get_estado_display(),
            str(op.monto_total),
            str(op.monto_retenciones),
            str(op.monto_neto),
            op.creado_en.strftime('%d/%m/%Y'),
            op.fecha_vencimiento.strftime('%d/%m/%Y') if op.fecha_vencimiento else '',
            op.fecha_pago.strftime('%d/%m/%Y') if op.fecha_pago else '',
            op.usuario.get_full_name() if op.usuario else '',
            op.usuario_aprobacion.get_full_name() if op.usuario_aprobacion else '',
            op.observaciones or '',
        ])
    return response


@require_POST
@login_required
@require_perm('Compras', 'Eliminar')
def anular_orden_pago(request, pk):
    op = get_object_or_404(OrdenPago, pk=pk)
    if op.estado != 'pagada':
        estado_anterior = op.estado
        op.estado = 'anulada'
        op.save(update_fields=['estado', 'actualizado_en'])
        _registrar_auditoria(request, op, estado_anterior, 'anulada')
        messages.success(request, f'Orden de Pago N° {op.numero} anulada.')
    else:
        messages.error(request, 'No se puede anular una orden ya pagada.')
    return redirect('compras:lista_ordenes_pago')
