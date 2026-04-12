from permisos.decorators import requiere_permiso
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
from decimal import Decimal
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.forms import formset_factory
import json

from .forms import (
    AltaPedidoHeaderForm,
    LineaPedidoForm,
    LineaPedidoFormSet,
    SeleccionarClienteForm,
    ModificarPedidoForm,
    PagoFacturaForm,
)
from .models import Pedido, EstadoPedido, LineaPedido, Factura, PagoFactura
from .utils import (
    verificar_insumos_disponibles,
    verificar_insumos_para_lineas,
    verificar_insumos_para_ajuste,
    ajustar_insumos_por_diferencia,
    calcular_insumos_bajo_minimo,
)
from productos.models import Producto
from proveedores.models import Proveedor
from insumos.models import Insumo
from .models import OrdenCompra
from configuracion.permissions import require_perm


def _get_iva_rate() -> Decimal:
    """Retorna la tasa de IVA configurada en Parametro (default: 0.21 = 21%)."""
    try:
        from configuracion.models import Parametro
        return Decimal(str(Parametro.get('IVA_PORCENTAJE', '0.21')))
    except Exception:
        return Decimal('0.21')


def _audit_pedido(request, pedido, accion, extra=None):
    """Registra un AuditEntry para un Pedido. Silencia errores."""
    try:
        from auditoria.models import AuditEntry
        import json
        AuditEntry.objects.create(
            user=request.user,
            ip_address=request.META.get('REMOTE_ADDR'),
            path=request.path,
            method=request.method,
            app_label='pedidos',
            model='Pedido',
            object_id=str(pedido.pk),
            object_repr=str(pedido),
            action=accion,
            changes=json.dumps(extra or {}),
        )
    except Exception:
        pass


@require_perm('Pedidos', 'Listar')
@login_required
@requiere_permiso("Pedidos")
def lista_pedidos(request):
    """Lista unificada con búsqueda, orden, paginación y filtro de fechas para Pedidos."""
    query       = (request.GET.get("q", "") or request.GET.get("criterio", "")).strip()
    order_by    = request.GET.get("order_by", "id")
    direction   = request.GET.get("direction", "desc")
    estado_fil  = request.GET.get("estado", "")
    fecha_desde = request.GET.get("fecha_desde", "")
    fecha_hasta = request.GET.get("fecha_hasta", "")

    valid_order_fields = [
        "id", "cliente__nombre", "cliente__apellido",
        "fecha_pedido", "fecha_entrega", "estado__nombre", "monto_total"
    ]
    if order_by not in valid_order_fields:
        order_by = "id"

    qs = Pedido.objects.select_related("cliente", "estado").prefetch_related("lineas__producto").filter(eliminado=False)

    if query:
        if query.isdigit():
            qs = qs.filter(Q(id=int(query)) |
                           Q(cliente__nombre__icontains=query) |
                           Q(cliente__apellido__icontains=query) |
                           Q(cliente__razon_social__icontains=query) |
                           Q(estado__nombre__icontains=query) |
                           Q(lineas__producto__nombreProducto__icontains=query)).distinct()
        else:
            qs = qs.filter(
                Q(cliente__nombre__icontains=query) |
                Q(cliente__apellido__icontains=query) |
                Q(cliente__razon_social__icontains=query) |
                Q(estado__nombre__icontains=query) |
                Q(lineas__producto__nombreProducto__icontains=query)
            ).distinct()

    if estado_fil:
        qs = qs.filter(estado__nombre__iexact=estado_fil)
    if fecha_desde:
        qs = qs.filter(fecha_pedido__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_pedido__lte=fecha_hasta)

    order_field = f"-{order_by}" if direction == "desc" else order_by
    qs = qs.order_by(order_field)

    from configuracion.services import get_page_size
    paginator = Paginator(qs, get_page_size())
    page_obj = paginator.get_page(request.GET.get("page"))
    total_resultados = paginator.count

    return render(request, "pedidos/lista_pedidos.html", {
        "pedidos": page_obj,
        "query": query,
        "order_by": order_by,
        "direction": direction,
        "estado_fil": estado_fil,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "estados": EstadoPedido.objects.all(),
        "total_resultados": total_resultados,
    })


@require_perm('Pedidos', 'Crear')
@login_required
@requiere_permiso("Pedidos", "Crear")
def alta_pedido(request):
    # Permitir precargar cliente vía querystring ?cliente=<id>
    initial = {}
    cliente_id = request.GET.get("cliente")
    if cliente_id:
        initial["cliente"] = cliente_id

    if request.method == "POST":
        header_form = AltaPedidoHeaderForm(request.POST)
        formset = LineaPedidoFormSet(request.POST, prefix="lineas")
        if header_form.is_valid() and formset.is_valid():
            cliente = header_form.cleaned_data["cliente"]
            fecha_entrega = header_form.cleaned_data["fecha_entrega"]
            aplicar_iva = header_form.cleaned_data.get("aplicar_iva", False)
            iva_rate = _get_iva_rate()
            iva_multiplier = (Decimal("1") + iva_rate) if aplicar_iva else Decimal("1")

            # Estado inicial Pendiente (crear si no existe)
            estado_pendiente, _ = EstadoPedido.objects.get_or_create(nombre="Pendiente")

            # Preparar líneas válidas (no borradas y con datos)
            lineas = []
            for f in formset:
                if f.cleaned_data.get("DELETE"):
                    continue
                producto = f.cleaned_data.get("producto")
                cantidad = f.cleaned_data.get("cantidad")
                especificaciones = f.cleaned_data.get("especificaciones")
                if not producto or not cantidad:
                    continue
                lineas.append((producto, cantidad, especificaciones))

            # Validación de insumos en conjunto (usa receta si existe)
            # Primero advertir si algún producto no tiene receta definida
            try:
                from productos.models import ProductoInsumo
                productos_sin_receta = [
                    p.nombreProducto for (p, _c, _e) in lineas
                    if not ProductoInsumo.objects.filter(producto=p).exists()
                ]
                if productos_sin_receta:
                    messages.warning(
                        request,
                        f"Los siguientes productos no tienen receta definida y deberían configurarse: {', '.join(productos_sin_receta)}"
                    )
            except Exception:
                pass

            # Requiere al menos un producto
            if not lineas:
                messages.error(request, "Debe agregar al menos un producto al pedido.")
                return render(request, "pedidos/alta_pedido.html", {
                    "header_form": header_form,
                    "formset": formset,
                    "fecha_pedido_hoy": timezone.now().date(),
                    "precios": {p.pk: float(p.precio) for p in Producto.objects.all()},
                    "productos_calculadora": list(
                        Producto.objects.filter(activo=True)
                        .order_by('nombreProducto')
                        .values('idProducto', 'nombreProducto', 'unidadMedida__simbolo', 'unidadMedida__nombre')
                    ),
                    "proximo_numero_pedido": (Pedido.objects.order_by('-id').first().id + 1) if Pedido.objects.exists() else 1,
                    "clientes_data_json": "[]",
                })

            ok, faltantes = verificar_insumos_para_lineas([(p, c) for (p, c, _e) in lineas])
            if not ok:
                if faltantes:
                    # Mostrar detalle con código y nombre de insumo cuando sea posible
                    try:
                        from insumos.models import Insumo
                        info = {
                            i.idInsumo: (i.codigo, i.nombre) for i in Insumo.objects.filter(idInsumo__in=faltantes.keys())
                        }
                    except Exception:
                        info = {}
                    detalle = ", ".join([
                        f"{info.get(iid, ('-', f'Insumo {iid}'))[0]} - "
                        f"{info.get(iid, ('-', f'Insumo {iid}'))[1]}: faltan {falt:.2f}"
                        for iid, falt in faltantes.items()
                    ])
                    messages.warning(request, f"No hay insumos suficientes: {detalle}. El pedido se guardó igualmente.")
                else:
                    messages.warning(request, "No hay insumos suficientes para las cantidades solicitadas. El pedido se guardó igualmente.")

            # Calcular subtotal antes de crear el pedido
            subtotal = Decimal("0")
            for producto, cantidad, especificaciones in lineas:
                line_total = (producto.precio or Decimal("0")) * cantidad
                subtotal += line_total

            descuento = Decimal(header_form.cleaned_data.get("descuento", 0))
            subtotal_con_descuento = subtotal * (1 - descuento / 100)
            total_con_iva = subtotal_con_descuento * iva_multiplier

            # Crear pedido en una transacción. El stock se descuenta cuando
            # el estado cambia a "proceso" (vía Pedido.save → reservar_insumos_para_pedido).
            with transaction.atomic():
                # Crear el pedido cabecera
                pedido = Pedido.objects.create(
                    cliente=cliente,
                    fecha_entrega=fecha_entrega,
                    estado=estado_pendiente,
                    monto_total=total_con_iva,
                    descuento=float(descuento),
                    aplicar_iva=aplicar_iva,
                )
                # Crear cada línea del pedido
                for producto, cantidad, especificaciones in lineas:
                    LineaPedido.objects.create(
                        pedido=pedido,
                        producto=producto,
                        cantidad=cantidad,
                        especificaciones=especificaciones,
                        precio_unitario=producto.precio or Decimal("0")
                    )

            _audit_pedido(request, pedido, 'create', {'lineas': len(lineas), 'total': str(total_con_iva)})
            cant_lineas = len([f for f in formset if not f.cleaned_data.get('DELETE')
                              and f.cleaned_data.get('producto') and f.cleaned_data.get('cantidad')])
            if aplicar_iva:
                messages.success(
                    request, f"Se registraron {cant_lineas} productos. Subtotal: ${subtotal:.2f} | Descuento: {descuento}% | Total c/IVA (21%): ${total_con_iva:.2f}")
            else:
                messages.success(request, f"Se registraron {cant_lineas} productos. Subtotal: ${subtotal:.2f} | Descuento: {descuento}% | Total: ${subtotal_con_descuento:.2f}")
            return redirect("lista_pedidos")
        else:
            messages.error(request, "Revisá los datos del formulario")
            form = header_form
    else:
        header_form = AltaPedidoHeaderForm(initial=initial)
        # Permitir precargar producto y cantidad desde el Dashboard: ?producto=<id>&cantidad=<n>
        pid = request.GET.get("producto")
        cant = request.GET.get("cantidad")
        formset_initial = []
        try:
            if pid and cant and int(cant) > 0:
                # Acepta PK directo para ModelChoiceField
                formset_initial = [{"producto": int(pid), "cantidad": int(cant)}]
        except Exception:
            formset_initial = []

        # Si viene prellenado, omitimos la fila extra en blanco (extra=0)
        if formset_initial:
            DynamicFormSet = formset_factory(LineaPedidoForm, extra=0, can_delete=True)
            formset = DynamicFormSet(prefix="lineas", initial=formset_initial)
        else:
            formset = LineaPedidoFormSet(prefix="lineas", initial=formset_initial)

    # Fecha de pedido mostrada en la UI, auto = hoy
    fecha_pedido_hoy = timezone.now().date()
    # Calcular el próximo número de pedido (id + 1)
    ultimo_pedido = Pedido.objects.order_by('-id').first()
    proximo_numero_pedido = (ultimo_pedido.id + 1) if ultimo_pedido else 1
    # Productos para calculadora en Alta (con unidad de medida)
    productos_calculadora = list(
        Producto.objects.filter(activo=True)
        .order_by('nombreProducto')
        .values('idProducto', 'nombreProducto', 'unidadMedida__simbolo', 'unidadMedida__nombre')
    )
    precios = {p.pk: float(p.precio) for p in Producto.objects.all()}

    # Exponer todos los datos de clientes para JS (id, nombre, apellido, razon_social, email, telefono, celular, ranking)
    from clientes.models import Cliente
    from automatizacion.models import RankingCliente

    # Construir mapa de ranking por cliente_id
    ranking_map = {
        cliente_id: score
        for cliente_id, score in RankingCliente.objects.values_list('cliente_id', 'score')
    }

    # S-7: leer umbrales y descuentos de Parametro para consistencia con presupuestos.
    from configuracion.models import Parametro as _Param
    try:
        _desc = {
            'nuevo':       int(_Param.get('DESCUENTO_CLIENTE_NUEVO',       0)),
            'estandar':    int(_Param.get('DESCUENTO_CLIENTE_ESTANDAR',    5)),
            'estrategico': int(_Param.get('DESCUENTO_CLIENTE_ESTRATEGICO', 15)),
            'premium':     int(_Param.get('DESCUENTO_CLIENTE_PREMIUM',     25)),
        }
        _umbrales = {
            'premium':     float(_Param.get('UMBRAL_TIER_PREMIUM',     90)),
            'estrategico': float(_Param.get('UMBRAL_TIER_ESTRATEGICO', 60)),
            'estandar':    float(_Param.get('UMBRAL_TIER_ESTANDAR',    30)),
        }
    except Exception:
        _desc = {'nuevo': 0, 'estandar': 5, 'estrategico': 15, 'premium': 25}
        _umbrales = {'premium': 90, 'estrategico': 60, 'estandar': 30}

    def _score_a_tier(score):
        if score is None:
            return {'tier': 'Sin ranking', 'descuento': 0, 'color': 'secondary'}
        if score >= _umbrales['premium']:
            return {'tier': 'Premium', 'descuento': _desc['premium'], 'color': 'warning'}
        if score >= _umbrales['estrategico']:
            return {'tier': 'Estratégico', 'descuento': _desc['estrategico'], 'color': 'primary'}
        if score >= _umbrales['estandar']:
            return {'tier': 'Estándar', 'descuento': _desc['estandar'], 'color': 'info'}
        return {'tier': 'Nuevo', 'descuento': _desc['nuevo'], 'color': 'success'}

    clientes_data = []
    for c in Cliente.objects.all():
        cuit = getattr(c, 'cuit', '')
        score = ranking_map.get(c.id)
        tier_info = _score_a_tier(score)
        clientes_data.append({
            "id": c.id,
            "nombre": c.nombre,
            "apellido": c.apellido,
            "razon_social": c.razon_social or "",
            "cuit": cuit or "",
            "email": c.email,
            "telefono": c.telefono,
            "celular": c.celular or "",
            "tipo_cliente": getattr(c, 'tipo_cliente', '') or '',
            "score": round(score, 2) if score is not None else None,
            "tier": tier_info['tier'],
            "descuento_ranking": tier_info['descuento'],
            "tier_color": tier_info['color'],
        })

    return render(
        request,
        "pedidos/alta_pedido.html",
        {
            "header_form": header_form,
            "formset": formset,
            "fecha_pedido_hoy": fecha_pedido_hoy,
            "precios": precios,
            "productos_calculadora": productos_calculadora,
            "proximo_numero_pedido": proximo_numero_pedido,
            "clientes_data_json": json.dumps(clientes_data),
        },
    )


@require_POST
@login_required
@requiere_permiso("Pedidos")
def verificar_stock(request):
    """Endpoint AJAX: valida stock para las líneas de un pedido antes de enviar.
    Espera JSON: { "lineas": [{"producto": <id>, "cantidad": <int>}, ...] }
    Responde: { ok: bool, faltantes: [{id, codigo, nombre, faltan}] }
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    lineas_req = body.get("lineas", []) or []
    if not isinstance(lineas_req, list):
        return JsonResponse({"ok": False, "error": "Formato inválido"}, status=400)

    # Construir (producto, cantidad)
    productos_by_id = {p.idProducto: p for p in Producto.objects.filter(
        idProducto__in=[l.get("producto") for l in lineas_req if l.get("producto")])}
    lineas = []
    for l in lineas_req:
        pid = l.get("producto")
        cant = l.get("cantidad") or 0
        prod = productos_by_id.get(pid)
        if prod and int(cant) > 0:
            lineas.append((prod, int(cant)))

    if not lineas:
        return JsonResponse({"ok": True, "faltantes": []})

    ok, faltantes = verificar_insumos_para_lineas(lineas)

    # Calcular insumos que quedarán bajo mínimo (advertencia, no bloqueo)
    try:
        bajo_minimo = calcular_insumos_bajo_minimo(lineas)
    except Exception:
        bajo_minimo = []

    if ok:
        return JsonResponse({"ok": True, "faltantes": [], "bajo_minimo": bajo_minimo})

    # Enriquecer faltantes con código y nombre si está disponible
    detalle = []
    if faltantes:
        try:
            from insumos.models import Insumo
            info = {i.idInsumo: (i.codigo, i.nombre) for i in Insumo.objects.filter(idInsumo__in=faltantes.keys())}
        except Exception:
            info = {}
        for iid, falt in faltantes.items():
            codigo, nombre = info.get(iid, ("-", f"Insumo {iid}"))
            detalle.append({"id": iid, "codigo": codigo, "nombre": nombre, "faltan": float(falt)})
    return JsonResponse({"ok": False, "faltantes": detalle, "bajo_minimo": []})


@require_POST
@login_required
@requiere_permiso("Pedidos")
def verificar_stock_modificar(request, idPedido: int):
    """Endpoint AJAX: valida stock para el ajuste neto de un pedido existente.
    Espera JSON: { "producto": <id>, "cantidad": <int> }
    Responde: { ok: bool, faltantes: [{id, codigo, nombre, faltan}] }
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    pedido = get_object_or_404(Pedido.objects.select_related("cliente", "estado"), pk=idPedido)
    producto_id = body.get("producto")
    cantidad = int(body.get("cantidad") or 0)

    if not producto_id or cantidad <= 0:
        # Si no hay datos, no bloquear
        return JsonResponse({"ok": True, "faltantes": []})

    try:
        prod = Producto.objects.get(pk=producto_id)
    except Producto.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Producto inválido"}, status=400)

    lineas_actuales = list(pedido.lineas.select_related('producto').all())
    old_lineas = [(l.producto, l.cantidad) for l in lineas_actuales]
    new_lineas = [(prod, cantidad)]
    ok, faltantes = verificar_insumos_para_ajuste(old_lineas, new_lineas)
    if ok:
        return JsonResponse({"ok": True, "faltantes": []})

    detalle = []
    if faltantes:
        try:
            from insumos.models import Insumo
            info = {i.idInsumo: (i.codigo, i.nombre) for i in Insumo.objects.filter(idInsumo__in=faltantes.keys())}
        except Exception:
            info = {}
        for iid, falt in faltantes.items():
            codigo, nombre = info.get(iid, ("-", f"Insumo {iid}"))
            detalle.append({"id": iid, "codigo": codigo, "nombre": nombre, "faltan": float(falt)})
    return JsonResponse({"ok": False, "faltantes": detalle})


@require_POST
@login_required
@requiere_permiso("Pedidos")
def verificar_stock_diferencial(request, idPedido: int):
    """Endpoint AJAX: valida el ajuste NETO de insumos para múltiples líneas nuevas.
    Usa verificar_insumos_para_ajuste (diferencial), correcto para pedidos En Proceso.
    Para la transición Pendiente → En Proceso usa verificar_insumos_para_lineas (absoluto).

    Espera JSON:
      { "lineas": [{"producto": <id>, "cantidad": <int>}, ...], "nuevo_estado_id": <int|null> }
    Responde: { ok: bool, faltantes: [{id, codigo, nombre, faltan}] }
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    pedido = get_object_or_404(Pedido.objects.select_related("estado"), pk=idPedido)
    lineas_req = body.get("lineas", []) or []
    if not isinstance(lineas_req, list):
        return JsonResponse({"ok": False, "error": "Formato inválido"}, status=400)

    productos_by_id = {p.idProducto: p for p in Producto.objects.filter(
        idProducto__in=[l.get("producto") for l in lineas_req if l.get("producto")])}
    new_lineas = []
    for l in lineas_req:
        pid = l.get("producto")
        cant = l.get("cantidad") or 0
        prod = productos_by_id.get(pid)
        if prod and int(cant) > 0:
            new_lineas.append((prod, int(cant)))

    if not new_lineas:
        return JsonResponse({"ok": True, "faltantes": []})

    old_lineas = [(lp.producto, lp.cantidad) for lp in pedido.lineas.select_related('producto').all()]

    # Detectar si el nuevo estado es "En Proceso" y el actual es "Pendiente"
    nuevo_estado_id = body.get("nuevo_estado_id")
    estado_actual_nombre = (pedido.estado.nombre or "").lower() if pedido.estado else ""
    es_transicion_a_proceso = False
    if nuevo_estado_id:
        try:
            nuevo_estado = EstadoPedido.objects.get(pk=nuevo_estado_id)
            nuevo_estado_nombre = (nuevo_estado.nombre or "").lower()
            es_transicion_a_proceso = (
                "pendiente" in estado_actual_nombre and "proceso" in nuevo_estado_nombre
            )
        except EstadoPedido.DoesNotExist:
            pass

    if es_transicion_a_proceso:
        ok, faltantes = verificar_insumos_para_lineas(new_lineas)
    else:
        ok, faltantes = verificar_insumos_para_ajuste(old_lineas, new_lineas)

    if ok:
        return JsonResponse({"ok": True, "faltantes": []})

    detalle = []
    if faltantes:
        try:
            info = {i.idInsumo: (i.codigo, i.nombre) for i in Insumo.objects.filter(idInsumo__in=faltantes.keys())}
        except Exception:
            info = {}
        for iid, falt in faltantes.items():
            codigo, nombre = info.get(iid, ("-", f"Insumo {iid}"))
            detalle.append({"id": iid, "codigo": codigo, "nombre": nombre, "faltan": float(falt)})
    return JsonResponse({"ok": False, "faltantes": detalle})


@require_POST
@login_required
@requiere_permiso("Pedidos")
def enviar_pedido_cliente(request, idPedido: int):
    """Envía la confirmación del pedido al email del cliente."""
    from django.core.mail import send_mail
    from django.conf import settings
    from django.template.loader import render_to_string

    pedido = get_object_or_404(
        Pedido.objects.select_related("cliente", "estado").prefetch_related("lineas__producto"),
        pk=idPedido,
    )
    cliente = pedido.cliente

    if not cliente.email:
        return JsonResponse({"ok": False, "error": "El cliente no tiene email registrado"}, status=400)

    lineas = pedido.lineas.select_related("producto").all()

    # Calcular desglose de montos
    subtotal = sum(
        (l.precio_unitario or Decimal("0")) * l.cantidad for l in lineas
    )
    monto_descuento = subtotal * (pedido.descuento / Decimal("100")) if pedido.descuento else Decimal("0")
    subtotal_con_descuento = subtotal - monto_descuento
    monto_iva = subtotal_con_descuento * _get_iva_rate() if pedido.aplicar_iva else Decimal("0")

    # Agregar subtotal por línea al contexto
    class LineaConSubtotal:
        def __init__(self, linea):
            self._linea = linea
            self.producto = linea.producto
            self.cantidad = linea.cantidad
            self.especificaciones = linea.especificaciones
            self.precio_unitario = linea.precio_unitario
            self.subtotal = (linea.precio_unitario or Decimal("0")) * linea.cantidad

    lineas_con_subtotal = [LineaConSubtotal(l) for l in lineas]

    try:
        html_body = render_to_string("pedidos/email_confirmacion_pedido.html", {
            "pedido": pedido,
            "cliente": cliente,
            "lineas": lineas_con_subtotal,
            "subtotal": subtotal,
            "monto_descuento": monto_descuento,
            "monto_iva": monto_iva,
        })
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("enviar_pedido_cliente: error al renderizar template: %s", exc)
        return JsonResponse({"ok": False, "error": "Error al preparar el email"}, status=500)

    productos_str = ", ".join(
        f"{l.producto.nombreProducto} (x{l.cantidad})" for l in lineas
    ) or "Ver detalle"

    texto_plano = (
        f"Hola {cliente.nombre},\n\n"
        f"Te confirmamos que recibimos tu pedido N° {pedido.pk}.\n\n"
        f"Productos: {productos_str}\n"
        f"Fecha de entrega estimada: {pedido.fecha_entrega}\n"
        f"Total: ${pedido.monto_total:,.2f}\n\n"
        f"Ante cualquier consulta, estamos a tu disposición.\n"
        f"— Imprenta Tucán"
    )

    try:
        send_mail(
            subject=f"Confirmación de Pedido N° {pedido.pk} — Imprenta Tucán",
            message=texto_plano,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[cliente.email],
            html_message=html_body,
            fail_silently=False,
        )
        return JsonResponse({"ok": True, "message": f"Email enviado a {cliente.email}"})
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("enviar_pedido_cliente: error al enviar email para pedido #%s: %s", pedido.pk, exc)
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)


@require_perm('Pedidos', 'Ver')
@login_required
@requiere_permiso("Pedidos")
def buscar_pedido(request):
    cliente_context = None
    pedidos = None
    if request.method == "POST":
        form = SeleccionarClienteForm(request.POST)
        if form.is_valid():
            cliente = form.cleaned_data["cliente"]
            cliente_context = cliente
            pedidos = (
                Pedido.objects.select_related("cliente", "estado")
                .filter(cliente=cliente)
                .order_by("-id")
            )
            if not pedidos.exists():
                from django.contrib import messages
                messages.error(request, "El cliente no tiene pedidos registrados")
    else:
        form = SeleccionarClienteForm()

    return render(request, "pedidos/buscar_pedido.html", {"form": form, "pedidos": pedidos, "cliente": cliente_context})


@require_perm('Pedidos', 'Ver')
@login_required
@requiere_permiso("Pedidos")
def detalle_pedido(request, pk: int):
    pedido = get_object_or_404(Pedido.objects.select_related("cliente", "estado"), pk=pk)
    lineas_qs = pedido.lineas.select_related("producto").all()
    lineas = []
    subtotal = Decimal("0")
    for l in lineas_qs:
        importe = l.precio_unitario * l.cantidad if l.precio_unitario is not None and l.cantidad is not None else Decimal("0")
        subtotal += importe
        lineas.append({
            "producto": l.producto,
            "cantidad": l.cantidad,
            "especificaciones": l.especificaciones,
            "precio_unitario": l.precio_unitario,
            "importe": importe,
        })
    # Usar el valor guardado como autoritativo (evita divergencias por recálculo)
    descuento = Decimal(str(getattr(pedido, 'descuento', 0)))
    aplicar_iva = getattr(pedido, 'aplicar_iva', False)
    subtotal_con_descuento = subtotal * (Decimal("1") - descuento / Decimal("100")) if descuento else subtotal
    iva_monto = (subtotal_con_descuento * _get_iva_rate()) if aplicar_iva else Decimal("0")
    return render(
        request,
        "pedidos/detalle_pedido.html",
        {
            "pedido": pedido,
            "lineas": lineas,
            "subtotal": subtotal,
            "descuento": descuento,
            "subtotal_con_descuento": subtotal_con_descuento,
            "aplicar_iva": aplicar_iva,
            "iva_monto": iva_monto,
            "monto_total": pedido.monto_total,  # valor guardado en BD = mismo que la lista
        },
    )


@require_perm('Pedidos', 'Editar')
@login_required
@requiere_permiso("Pedidos", "Editar")
def modificar_pedido(request, idPedido: int):
    """Permite modificar un pedido existente.

    Flujo:
    - Carga datos actuales en el formulario.
    - Al enviar, valida insumos disponibles.
    - Recalcula monto_total (precio x cantidad) y guarda.
    - Muestra mensajes de éxito o error.
    """
    pedido = get_object_or_404(Pedido.objects.select_related("cliente", "estado"), pk=idPedido)
    lineas_actuales = list(pedido.lineas.select_related('producto').all())

    if request.method == "POST":
        estado_nombre = (pedido.estado.nombre or "").lower() if pedido.estado else ""
        if estado_nombre == "entregado":
            messages.error(request, f"El pedido #{pedido.id} no puede modificarse porque ya fue Entregado.")
            return redirect(request.path)
        formset = LineaPedidoFormSet(request.POST, prefix="linea")
        form = ModificarPedidoForm(request.POST)
        if form.is_valid() and formset.is_valid():
            estado = form.cleaned_data["estado"]
            fecha_entrega = form.cleaned_data["fecha_entrega"]
            aplicar_iva = form.cleaned_data.get("aplicar_iva", False)
            descuento = form.cleaned_data.get("descuento", "0")
            new_lineas = []
            for f in formset.cleaned_data:
                if f and not f.get('DELETE', False):
                    new_lineas.append((f["producto"], f["cantidad"]))

            old_lineas = [(l.producto, l.cantidad) for l in lineas_actuales]

            estado_actual_nombre = (pedido.estado.nombre or "").lower() if pedido.estado else ""
            estado_nuevo_nombre = (estado.nombre or "").lower()

            # Completado y Entregado solo se pueden alcanzar desde En Proceso
            _estados_terminacion = ("complet", "entreg")
            if any(s in estado_nuevo_nombre for s in _estados_terminacion) and "proceso" not in estado_actual_nombre:
                messages.error(
                    request,
                    f"No se puede pasar a '{estado.nombre}' desde '{pedido.estado.nombre}'. "
                    f"El pedido debe estar en 'En Proceso' primero."
                )
                return redirect(request.path)

            # Elegir qué tipo de validación corresponde:
            # - Pendiente → En Proceso: el stock aún no se consumió; Pedido.save()
            #   llamará reservar_insumos_para_pedido (descuento total). Usar check absoluto.
            # - Cualquier otro caso (ej: En Proceso → En Proceso): el stock ya fue consumido
            #   al reservar, solo importa el NETO del cambio. Usar check diferencial.
            if "pendiente" in estado_actual_nombre and "proceso" in estado_nuevo_nombre:
                ok_stock, faltantes_stock = verificar_insumos_para_lineas(new_lineas)
            else:
                ok_stock, faltantes_stock = verificar_insumos_para_ajuste(old_lineas, new_lineas)

            # Bloquear si hay insumos faltantes, EXCEPTO cuando el nuevo estado es "Pendiente"
            if not ok_stock and estado_nuevo_nombre != "pendiente":
                if faltantes_stock:
                    try:
                        from insumos.models import Insumo
                        info = {i.idInsumo: (i.codigo, i.nombre)
                                for i in Insumo.objects.filter(idInsumo__in=faltantes_stock.keys())}
                    except Exception:
                        info = {}
                    detalle = ", ".join([
                        f"{info.get(iid, ('-', f'Insumo {iid}'))[1]}: faltan {falt:.2f}"
                        for iid, falt in faltantes_stock.items()
                    ])
                    messages.error(
                        request,
                        f"No se puede guardar el pedido: insumos insuficientes ({detalle})."
                    )
                else:
                    messages.error(
                        request,
                        "No se puede guardar el pedido: insumos insuficientes para las cantidades ingresadas."
                    )
                return redirect(request.path)

            # Calcular monto_total aplicando descuento e IVA igual que en alta_pedido
            subtotal = Decimal("0")
            for f in formset.cleaned_data:
                if f and not f.get('DELETE', False):
                    producto = f["producto"]
                    cantidad = f["cantidad"]
                    subtotal += (producto.precio or Decimal("0")) * cantidad

            descuento_val = Decimal(str(descuento))
            subtotal_con_descuento = subtotal * (1 - descuento_val / Decimal("100"))
            iva_multiplier = (Decimal("1") + _get_iva_rate()) if aplicar_iva else Decimal("1")
            monto_total = subtotal_con_descuento * iva_multiplier

            try:
                with transaction.atomic():
                    ajustar_insumos_por_diferencia(old_lineas, new_lineas)
                    # Reemplazar líneas del pedido
                    pedido.lineas.all().delete()
                    for f in formset.cleaned_data:
                        if f and not f.get('DELETE', False):
                            LineaPedido.objects.create(
                                pedido=pedido,
                                producto=f["producto"],
                                cantidad=f["cantidad"],
                                especificaciones=f.get("especificaciones", ""),
                                precio_unitario=f["producto"].precio or Decimal("0"),
                            )
                    pedido.estado = estado
                    pedido.fecha_entrega = fecha_entrega
                    pedido.descuento = descuento_val
                    pedido.aplicar_iva = aplicar_iva
                    pedido.monto_total = monto_total
                    pedido.save()
            except ValueError as e:
                messages.error(request, f"No se pudo cambiar el estado: {e}")
                return redirect(request.path)

            messages.success(request, "El pedido ha sido modificado correctamente.")
            return redirect("lista_pedidos")
        else:
            # Detectar si hay error de cantidad fuera de rango
            cantidad_error = any(
                form_linea.errors.get('cantidad') for form_linea in formset.forms
            )
            if cantidad_error:
                messages.error(request, "La cantidad por línea debe ser entre 1 y 1.000.000.")
            else:
                messages.error(request, "Revisá los datos del formulario.")
            return redirect(request.path)
    else:
        # Precargar con datos actuales
        initial_lineas = [
            {
                "producto": l.producto,
                "cantidad": l.cantidad,
                "especificaciones": l.especificaciones,
            }
            for l in lineas_actuales
        ]
        formset = LineaPedidoFormSet(initial=initial_lineas, prefix="linea")
        # Fecha de entrega: N días después de fecha_pedido si no está seteada (configurable en Parametro)
        from datetime import timedelta
        try:
            from configuracion.models import Parametro as _P
            _dias_entrega = int(_P.get('PEDIDO_DIAS_ENTREGA_DEFAULT', 10))
        except Exception:
            _dias_entrega = 10
        fecha_entrega_default = pedido.fecha_entrega or (pedido.fecha_pedido + timedelta(days=_dias_entrega))
        form = ModificarPedidoForm(initial={
            "estado": pedido.estado,
            "fecha_entrega": fecha_entrega_default,
        })

    precios = {p.pk: float(p.precio) for p in Producto.objects.all()}
    precios_lineas_json = json.dumps([float(l.precio_unitario) for l in lineas_actuales])

    # Calcular desglose inicial para mostrarlo desde el servidor (sin JS en la carga)
    _D = Decimal  # alias corto para legibilidad en cálculos de esta vista
    subtotal_inicial = sum(
        (l.precio_unitario if l.precio_unitario else (l.producto.precio or _D("0"))) * l.cantidad
        for l in lineas_actuales
    )
    descuento_bd = _D(str(pedido.descuento or 0))
    monto_descuento_inicial = (subtotal_inicial * descuento_bd / _D("100")).quantize(_D("0.01"))
    subtotal_con_desc = subtotal_inicial - monto_descuento_inicial
    monto_iva_inicial = (subtotal_con_desc * _get_iva_rate()).quantize(_D("0.01")) if pedido.aplicar_iva else _D("0")

    descuento_actual = int(float(pedido.descuento)) if pedido.descuento else 0
    aplicar_iva_actual = bool(pedido.aplicar_iva)

    # Mostrar desglose (descuento/IVA) solo si monto_total coincide con la fórmula.
    # Para pedidos viejos (monto_total = solo la suma de líneas), ocultarlo evita confusión.
    total_calculado = subtotal_con_desc * (_D("1") + _get_iva_rate() if aplicar_iva_actual else _D("1"))
    mostrar_desglose = abs(total_calculado - pedido.monto_total) < _D("1")

    return render(request, "pedidos/modificar_pedido.html", {
        "form": form,
        "formset": formset,
        "pedido": pedido,
        "precios": precios,
        "precios_lineas_json": precios_lineas_json,
        "estados": EstadoPedido.objects.all(),
        "productos": Producto.objects.filter(activo=True).order_by('nombreProducto'),
        "fecha_entrega": pedido.fecha_entrega.strftime('%Y-%m-%d') if pedido.fecha_entrega else '',
        "descuento_actual": descuento_actual,
        "mostrar_desglose": mostrar_desglose,
        "aplicar_iva_actual": aplicar_iva_actual,
        "subtotal_inicial": subtotal_inicial,
        "monto_descuento_inicial": monto_descuento_inicial,
        "monto_iva_inicial": monto_iva_inicial,
    })


@require_perm('Pedidos', 'Eliminar')
@login_required
@requiere_permiso("Pedidos", "Eliminar")
def eliminar_pedido(request, idPedido: int):
    """Baja lógica del pedido — marca eliminado=True sin borrar el registro."""
    pedido = get_object_or_404(Pedido.objects.select_related("cliente", "estado"), pk=idPedido)
    if request.method == "POST":
        if not request.user.is_staff:
            messages.error(request, "No tenés permisos para dar de baja pedidos.")
            return redirect("lista_pedidos")
        estado_nombre = (pedido.estado.nombre or "").lower() if pedido.estado else ""
        if estado_nombre not in ("cancelado", "entregado"):
            messages.error(
                request,
                f"El pedido #{pedido.id} no puede darse de baja porque su estado es "
                f"'{pedido.estado}'. Solo se pueden dar de baja pedidos Cancelados o Entregados."
            )
            return redirect("lista_pedidos")
        descripcion = f"Pedido {pedido.id} - {pedido.cliente}"
        _audit_pedido(request, pedido, 'delete', {'estado': pedido.estado.nombre, 'total': str(pedido.monto_total)})
        pedido.eliminado = True
        pedido.save(update_fields=['eliminado'])
        messages.success(request, f"{descripcion} fue dado de baja correctamente.")
        return redirect("lista_pedidos")
    return redirect("lista_pedidos")


@require_perm('Pedidos', 'Ver')
@login_required
@requiere_permiso("Pedidos")
def orden_compra_detalle(request, pk):
    orden = OrdenCompra.objects.select_related('proveedor', 'insumo').get(pk=pk)
    proveedor = orden.proveedor
    # Datos de la empresa (puedes reemplazar por tu modelo/config real)
    empresa = {
        'razon_social': 'Imprenta Tucán S.A.',
        'cuit': '30-12345678-9',
        'domicilio': 'Av. Principal 123, Tucumán',
        'telefono': '381-4000000',
        'email': 'info@imprentatucan.com',
        'condicion_iva': 'Responsable Inscripto',
    }
    # Cálculos
    precio_unitario = orden.insumo.precio_unitario
    subtotal = float(precio_unitario) * orden.cantidad
    iva = subtotal * 0.21
    total = subtotal + iva
    context = {
        'orden': orden,
        'proveedor': proveedor,
        'empresa': empresa,
        'precio_unitario': '{:.2f}'.format(float(precio_unitario)) if precio_unitario else None,
        'subtotal': '{:.2f}'.format(subtotal),
        'iva': '{:.2f}'.format(iva),
        'total': '{:.2f}'.format(total),
        'stock_actual': getattr(orden.insumo, 'stock', None),
        'stock_minimo': getattr(orden.insumo, 'stock_minimo', None),
    }
    return render(request, 'pedidos/orden_compra_detalle.html', context)


@login_required
@requiere_permiso("Pedidos", "Crear")
def clonar_pedido(request, pk):
    """Crea un pedido nuevo con los mismos productos/cantidades, estado Pendiente."""
    original = get_object_or_404(Pedido.objects.prefetch_related('lineas__producto'), pk=pk)
    from datetime import date, timedelta
    from configuracion.models import Parametro as _P
    _dias_entrega = int(_P.get('PEDIDO_DIAS_ENTREGA_DEFAULT', 10))
    estado_pendiente, _ = EstadoPedido.objects.get_or_create(nombre='Pendiente')
    with transaction.atomic():
        nuevo = Pedido.objects.create(
            cliente=original.cliente,
            fecha_entrega=date.today() + timedelta(days=_dias_entrega),
            estado=estado_pendiente,
            monto_total=original.monto_total,
            descuento=original.descuento,
            aplicar_iva=original.aplicar_iva,
        )
        for linea in original.lineas.all():
            LineaPedido.objects.create(
                pedido=nuevo,
                producto=linea.producto,
                cantidad=linea.cantidad,
                especificaciones=linea.especificaciones or '',
                precio_unitario=linea.precio_unitario,
            )
    _audit_pedido(request, nuevo, 'create', {'clonado_de': original.pk})
    messages.success(request, f'Pedido #{original.pk} clonado como #{nuevo.pk}. Revisá fecha de entrega.')
    return redirect('modificar_pedido', idPedido=nuevo.pk)


@login_required
@requiere_permiso("Pedidos")
def descargar_factura(request, idPedido: int):
    """Descarga el PDF de la factura asociada al pedido.
    Si el pedido aún no tiene factura (p. ej. estado no es Entregado),
    genera una al vuelo sin persistirla.
    """
    from .services import generar_pdf_factura, crear_factura_para_pedido

    pedido = get_object_or_404(
        Pedido.objects.select_related('cliente', 'estado').prefetch_related('lineas__producto'),
        pk=idPedido,
    )

    factura = getattr(pedido, 'factura', None)
    if factura is None:
        # Generar y persistir si el pedido está Entregado; de lo contrario solo generar en memoria
        estado_nombre = (pedido.estado.nombre or '').lower() if pedido.estado else ''
        if 'entreg' in estado_nombre:
            factura = crear_factura_para_pedido(pedido)
        else:
            # Vista previa sin persistir
            from .models import Factura as _F
            from django.utils import timezone as _tz
            factura = _F(
                pedido=pedido,
                numero=_F.proximo_numero(),
                fecha_emision=_tz.now(),
                monto_total=pedido.monto_total,
            )

    try:
        pdf_bytes = generar_pdf_factura(factura)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception('descargar_factura: error generando PDF para pedido #%s', idPedido)
        messages.error(request, f'No se pudo generar el PDF de la factura: {exc}')
        return redirect('detalle_pedido', pk=idPedido)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="factura_{factura.numero}.pdf"'
    )
    return response


@login_required
@requiere_permiso("Pedidos")
def exportar_pedidos_csv(request):
    """Exporta la lista de pedidos a CSV respetando los filtros activos."""
    import csv
    from django.http import HttpResponse

    query   = (request.GET.get('q', '') or request.GET.get('criterio', '')).strip()
    estado  = request.GET.get('estado', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')

    qs = Pedido.objects.select_related('cliente', 'estado').prefetch_related('lineas__producto').order_by('-id')
    if query:
        if query.isdigit():
            qs = qs.filter(Q(id=int(query)) | Q(cliente__nombre__icontains=query) | Q(cliente__apellido__icontains=query)).distinct()
        else:
            qs = qs.filter(Q(cliente__nombre__icontains=query) | Q(cliente__apellido__icontains=query) | Q(estado__nombre__icontains=query)).distinct()
    if estado:
        qs = qs.filter(estado__nombre__iexact=estado)
    if fecha_desde:
        qs = qs.filter(fecha_pedido__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_pedido__lte=fecha_hasta)

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="pedidos.csv"'
    writer = csv.writer(response)
    writer.writerow(['N° Pedido', 'Cliente', 'CUIT', 'Productos', 'Fecha Pedido', 'Fecha Entrega', 'Estado', 'Descuento %', 'IVA', 'Total'])
    for p in qs:
        productos = '; '.join(f"{l.producto.nombreProducto} x{l.cantidad}" for l in p.lineas.all())
        writer.writerow([
            p.pk,
            f"{p.cliente.nombre} {p.cliente.apellido}",
            p.cliente.cuit or '',
            productos,
            p.fecha_pedido.strftime('%d/%m/%Y'),
            p.fecha_entrega.strftime('%d/%m/%Y'),
            p.estado.nombre,
            p.descuento,
            '21%' if p.aplicar_iva else 'No',
            str(p.monto_total),
        ])
    return response


@require_POST
@login_required
@requiere_permiso("Pedidos")
def cambiar_estado_pedido(request, idPedido: int):
    """Cambia el estado de un pedido desde la lista de pedidos."""
    nuevo_estado_id = request.POST.get('nuevo_estado')

    if not nuevo_estado_id:
        messages.error(request, "Debe seleccionar un estado.")
        return redirect('lista_pedidos')

    try:
        with transaction.atomic():
            pedido = Pedido.objects.select_related('estado').get(pk=idPedido)
            nuevo_estado = EstadoPedido.objects.get(pk=nuevo_estado_id)

            estado_anterior = pedido.estado
            old_nombre = estado_anterior.nombre.lower() if estado_anterior else ""
            new_nombre = nuevo_estado.nombre.lower()

            # Completado y Entregado solo se pueden alcanzar desde En Proceso
            _estados_terminacion = ("complet", "entreg")
            if any(s in new_nombre for s in _estados_terminacion) and "proceso" not in old_nombre:
                messages.error(
                    request,
                    f"No se puede pasar a '{nuevo_estado.nombre}' desde '{estado_anterior.nombre}'. "
                    f"El pedido debe estar en 'En Proceso' primero."
                )
                return redirect('lista_pedidos')

            pedido.estado = nuevo_estado
            pedido.save()
            _audit_pedido(request, pedido, 'update', {'estado': [estado_anterior.nombre, nuevo_estado.nombre]})

            _estados_con_stock = ("proceso", "complet", "entreg")
            if "cancelad" in new_nombre and any(s in old_nombre for s in _estados_con_stock):
                messages.success(
                    request,
                    f"Pedido #{pedido.id} cancelado. El stock consumido fue devuelto al inventario."
                )
            else:
                messages.success(
                    request,
                    f"Pedido #{pedido.id} cambiado de '{estado_anterior.nombre}' a '{nuevo_estado.nombre}'."
                )

    except Pedido.DoesNotExist:
        messages.error(request, "Pedido no encontrado.")
    except EstadoPedido.DoesNotExist:
        messages.error(request, "Estado no válido.")
    except Exception as e:
        messages.error(request, f"Error al cambiar estado: {str(e)}")

    return redirect('lista_pedidos')


# ─────────────────────────────────────────────────────────────────────────────
# FACTURAS Y REGISTRO DE PAGOS
# ─────────────────────────────────────────────────────────────────────────────

@require_perm('Pedidos', 'Ver')
@login_required
@requiere_permiso("Pedidos")
def lista_facturas(request):
    """Lista todas las facturas con su estado de cobro."""
    from django.db.models import Sum, Value, DecimalField
    from django.db.models.functions import Coalesce

    qs = (
        Factura.objects
        .select_related('pedido__cliente', 'pedido__estado')
        .prefetch_related('pagos')
        .order_by('-fecha_emision')
    )

    # Filtros
    q = request.GET.get('q', '').strip()
    estado_fil = request.GET.get('estado_pago', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')

    if q:
        qs = qs.filter(
            Q(numero__icontains=q)
            | Q(pedido__cliente__nombre__icontains=q)
            | Q(pedido__cliente__apellido__icontains=q)
        )
    if fecha_desde:
        qs = qs.filter(fecha_emision__date__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_emision__date__lte=fecha_hasta)

    # Anotar total pagado para filtrar por estado
    qs = qs.annotate(
        total_pagado_sum=Coalesce(
            Sum('pagos__monto'), Value(0, output_field=DecimalField())
        )
    )

    # Filtrar por estado_pago en Python (más simple que SQL complejo)
    facturas_all = list(qs)
    if estado_fil:
        facturas_all = [f for f in facturas_all if f.estado_pago == estado_fil]

    total_resultados = len(facturas_all)

    # Paginación
    paginator = Paginator(facturas_all, 20)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    return render(request, 'pedidos/lista_facturas.html', {
        'facturas': page_obj,
        'total_resultados': total_resultados,
        'query': q,
        'estado_fil': estado_fil,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    })


@require_perm('Pedidos', 'Ver')
@login_required
@requiere_permiso("Pedidos")
def detalle_factura(request, pk: int):
    """Detalle de una factura con historial de pagos y formulario para registrar uno nuevo."""
    factura = get_object_or_404(
        Factura.objects.select_related('pedido__cliente', 'pedido__estado')
                       .prefetch_related('pagos', 'pedido__lineas__producto'),
        pk=pk,
    )

    if request.method == 'POST':
        form = PagoFacturaForm(request.POST)
        if form.is_valid():
            pago = form.save(commit=False)
            pago.factura = factura
            # Validar que no supere el saldo pendiente
            if pago.monto > factura.saldo_pendiente:
                messages.error(
                    request,
                    f'El monto ${pago.monto:,.2f} supera el saldo pendiente '
                    f'${factura.saldo_pendiente:,.2f}.'
                )
                return redirect('detalle_factura', pk=pk)
            pago.save()
            messages.success(
                request,
                f'Pago de ${pago.monto:,.2f} registrado correctamente. '
                f'Saldo restante: ${factura.saldo_pendiente:,.2f}'
            )
            return redirect('detalle_factura', pk=pk)
        else:
            messages.error(request, 'Revisá los datos del formulario.')
    else:
        # Pre-completar con el saldo pendiente como monto sugerido
        form = PagoFacturaForm(initial={
            'fecha_pago': timezone.now().date(),
            'monto': factura.saldo_pendiente,
        })

    pagos = factura.pagos.order_by('fecha_pago', 'registrado_en')

    return render(request, 'pedidos/detalle_factura.html', {
        'factura': factura,
        'pedido': factura.pedido,
        'pagos': pagos,
        'form': form,
    })


@require_POST
@require_perm('Pedidos', 'Editar')
@login_required
@requiere_permiso("Pedidos", "Editar")
def eliminar_pago(request, pk: int):
    """Elimina un pago registrado (corrección de error)."""
    pago = get_object_or_404(PagoFactura, pk=pk)
    factura_pk = pago.factura_id
    monto = pago.monto
    pago.delete()
    messages.success(request, f'Pago de ${monto:,.2f} eliminado.')
    return redirect('detalle_factura', pk=factura_pk)
