from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from usuarios.models import Usuario
from roles.models import Rol
from clientes.models import Cliente
from productos.models import Producto
from proveedores.models import Proveedor
from insumos.models import Insumo
from pedidos.models import Pedido
from presupuestos.models import Presupuesto
from auditoria.models import AuditEntry
from configuracion.models import Parametro
from compras.models import OrdenPago

# Vista principal protegida


@login_required
def inicio(request):
    return render(request, 'inicio.html')

# Dashboard con resumen de actividad (sin suposiciones de campos inexistentes)


@login_required
def dashboard(request):
    # Totales por módulo
    total_usuarios = Usuario.objects.count()
    total_roles = Rol.objects.count()
    total_clientes = Cliente.objects.count()
    total_productos = Producto.objects.count()
    total_proveedores = Proveedor.objects.count()
    total_insumos = Insumo.objects.count()
    total_pedidos = Pedido.objects.count()
    total_presupuestos = Presupuesto.objects.count()
    total_auditoria = AuditEntry.objects.count()
    total_configuracion = Parametro.objects.count()

    # Métricas de Órdenes de Pago y Compras
    from django.db.models import Sum
    from django.utils import timezone as tz
    from datetime import timedelta
    from compras.models import OrdenCompra as _OC
    hoy = tz.localdate()
    inicio_mes = hoy.replace(day=1)
    pagos_pendientes = OrdenPago.objects.filter(estado__in=['pendiente', 'aprobada'])
    pagos_pendientes_monto = pagos_oc_mes = 0
    try:
        pagos_pendientes_monto = pagos_pendientes.aggregate(t=Sum('monto_neto'))['t'] or 0
        pagos_oc_mes = OrdenPago.objects.filter(estado='pagada', fecha_pago__gte=inicio_mes).aggregate(t=Sum('monto_neto'))['t'] or 0
    except Exception:
        pass

    # L — Métricas de compras en curso para el dashboard
    oc_pendientes_entrega = 0
    oc_sin_respuesta = 0
    pagos_por_vencer_7d = 0
    pagos_vencidos = 0
    try:
        oc_pendientes_entrega = _OC.objects.exclude(
            estado__nombre__icontains='recibid'
        ).exclude(estado__nombre__icontains='cancelad').count()
        oc_sin_respuesta = _OC.objects.filter(
            enviada=True, fecha_recepcion__isnull=True
        ).count()
        pagos_por_vencer_7d = OrdenPago.objects.filter(
            estado__in=['pendiente', 'aprobada'],
            fecha_vencimiento__gte=hoy,
            fecha_vencimiento__lte=hoy + timedelta(days=7),
        ).count()
        pagos_vencidos = OrdenPago.objects.filter(
            estado__in=['pendiente', 'aprobada'],
            fecha_vencimiento__lt=hoy,
        ).count()
    except Exception:
        pass

    # Últimas fechas conocidas (cuando existan los campos)
    ultima_fecha_usuarios = (
        Usuario.objects.order_by('-date_joined').first().date_joined if Usuario.objects.exists() else None
    )
    # Cliente/Producto no tienen fecha de creación en el modelo actual
    ultima_fecha_clientes = None
    ultima_fecha_productos = None
    ultima_fecha_roles = None
    ultima_fecha_proveedores = (
        Proveedor.objects.order_by('-fecha_creacion').first().fecha_creacion if Proveedor.objects.exists() else None
    )
    ultima_fecha_insumos = (
        Insumo.objects.order_by('-created_at').first().created_at if Insumo.objects.exists() else None
    )
    ultima_fecha_pedidos = (
        Pedido.objects.order_by('-fecha_pedido').first().fecha_pedido if Pedido.objects.exists() else None
    )

    # Facturas pendientes de cobro
    facturas_pendientes = 0
    try:
        from pedidos.models import Factura
        from django.db.models import Sum as _Sum
        _ids_pagadas = [
            f.pk for f in Factura.objects.prefetch_related('pagos').annotate(
                _pagado=_Sum('pagos__monto')
            ) if (f._pagado or 0) >= f.monto_total
        ]
        facturas_pendientes = Factura.objects.exclude(pk__in=_ids_pagadas).count()
    except Exception:
        pass

    context = {
        'total_usuarios': total_usuarios,
        'total_roles': total_roles,
        'total_clientes': total_clientes,
        'total_productos': total_productos,
        'total_proveedores': total_proveedores,
        'total_insumos': total_insumos,
        'total_pedidos': total_pedidos,
        'total_presupuestos': total_presupuestos,
        'total_auditoria': total_auditoria,
        'total_configuracion': total_configuracion,
        'ultima_fecha_usuarios': ultima_fecha_usuarios,
        'ultima_fecha_clientes': ultima_fecha_clientes,
        'ultima_fecha_productos': ultima_fecha_productos,
        'ultima_fecha_roles': ultima_fecha_roles,
        'ultima_fecha_proveedores': ultima_fecha_proveedores,
        'ultima_fecha_insumos': ultima_fecha_insumos,
        'ultima_fecha_pedidos': ultima_fecha_pedidos,
        'pagos_pendientes_count': pagos_pendientes.count(),
        'pagos_pendientes_monto': pagos_pendientes_monto,
        'pagos_pagados_mes':      pagos_oc_mes,
        # L — Compras en curso
        'oc_pendientes_entrega':  oc_pendientes_entrega,
        'oc_sin_respuesta':       oc_sin_respuesta,
        'pagos_por_vencer_7d':    pagos_por_vencer_7d,
        'pagos_vencidos':         pagos_vencidos,
        'facturas_pendientes':    facturas_pendientes,
    }
    # Usar el dashboard con paneles inteligentes y logs
    return render(request, 'usuarios/dashboard_paneles.html', context)

# Vista para confirmar y ejecutar la eliminación de un cliente


@login_required
def confirmar_eliminacion_cliente(request, id):
    cliente = get_object_or_404(Cliente, id=id)

    if request.method == 'POST':
        nombre = f"{cliente.nombre} {cliente.apellido}"
        cliente.estado = 'Inactivo'
        cliente.save()
        messages.success(request, f"El cliente {nombre} fue desactivado correctamente.")
        return redirect('buscar_cliente')

    return render(request, 'clientes/confirmar_eliminacion.html', {'cliente': cliente})

# Vista para buscar clientes y mostrar resultados


@login_required
def buscar_cliente(request):
    criterio = request.GET.get('criterio', '')
    clientes = Cliente.objects.all()

    if criterio:
        clientes = clientes.filter(
            nombre__icontains=criterio
        ) | clientes.filter(
            apellido__icontains=criterio
        ) | clientes.filter(
            razon_social__icontains=criterio
        ) | clientes.filter(
            email__icontains=criterio
        ) | clientes.filter(
            telefono__icontains=criterio
        )

    return render(request, 'clientes/buscar_clientes.html', {
        'clientes': clientes,
        'criterio': criterio
    })


# Política de Privacidad
@login_required
def privacidad(request):
    return render(request, 'privacidad.html')
