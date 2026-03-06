from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.forms import formset_factory
import json

from .forms import (
    AltaPedidoHeaderForm,
    LineaPedidoForm,
    LineaPedidoFormSet,
    SeleccionarClienteForm,
    ModificarPedidoForm,
)
from .models import Pedido, EstadoPedido
from .models import LineaPedido
from .utils import (
    verificar_insumos_disponibles,
    verificar_insumos_para_lineas,
    descontar_insumos_para_lineas,
    verificar_insumos_para_ajuste,
    ajustar_insumos_por_diferencia,
)
from productos.models import Producto
from proveedores.models import Proveedor
from insumos.models import Insumo
from .models import OrdenCompra
from configuracion.permissions import require_perm


@require_perm('Pedidos', 'Listar')
def lista_pedidos(request):
    """Lista unificada con búsqueda, orden y paginación para Pedidos."""
    query = (request.GET.get("q", "") or request.GET.get("criterio", "")).strip()
    order_by = request.GET.get("order_by", "id")
    direction = request.GET.get("direction", "desc")

    valid_order_fields = [
        "id", "cliente__nombre", "cliente__apellido",
        "fecha_pedido", "fecha_entrega", "estado__nombre", "monto_total"
    ]
    if order_by not in valid_order_fields:
        order_by = "id"

    qs = Pedido.objects.select_related("cliente", "estado").prefetch_related("lineas__producto")

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

    order_field = f"-{order_by}" if direction == "desc" else order_by
    qs = qs.order_by(order_field)

    from configuracion.services import get_page_size
    paginator = Paginator(qs, get_page_size())
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "pedidos/lista_pedidos.html",
        {
            "pedidos": page_obj,
            "query": query,
            "order_by": order_by,
            "direction": direction,
        },
    )


@require_perm('Pedidos', 'Crear')
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
            iva_multiplier = Decimal("1.21") if aplicar_iva else Decimal("1")

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
                        .values('idProducto', 'nombreProducto', 'unidadMedida__abreviatura', 'unidadMedida__nombreUnidad')
                    ),
                    "proximo_numero_pedido": (Pedido.objects.order_by('-id').first().id + 1) if Pedido.objects.exists() else 1,
                    "clientes_data": [],
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

            # Descontar stock y crear pedidos en una transacción
            with transaction.atomic():
                descontar_insumos_para_lineas([(p, c) for (p, c, _e) in lineas])
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
        .values('idProducto', 'nombreProducto', 'unidadMedida__abreviatura', 'unidadMedida__nombreUnidad')
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

    def _score_a_tier(score):
        if score is None:
            return {'tier': 'Sin ranking', 'descuento': 0, 'color': 'secondary'}
        if score >= 90:
            return {'tier': 'Premium', 'descuento': 15, 'color': 'warning'}
        if score >= 60:
            return {'tier': 'Estratégico', 'descuento': 10, 'color': 'primary'}
        if score >= 30:
            return {'tier': 'Estándar', 'descuento': 7, 'color': 'info'}
        return {'tier': 'Nuevo', 'descuento': 5, 'color': 'success'}

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
            "clientes_data": clientes_data,
        },
    )


@require_POST
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
    if ok:
        return JsonResponse({"ok": True, "faltantes": []})

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
    return JsonResponse({"ok": False, "faltantes": detalle})


@require_POST
def verificar_stock_modificar(request, idPedido: int):
    """Endpoint AJAX: valida stock para el ajuste neto de un pedido existente.
    Espera JSON: { "producto": <id>, "cantidad": <int> }
    Responde: { ok: bool, faltantes: [{id, codigo, nombre, faltan}] }
    """
    from django.shortcuts import get_object_or_404

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


@require_perm('Pedidos', 'Ver')
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
def detalle_pedido(request, pk: int):
    from django.shortcuts import get_object_or_404

    pedido = get_object_or_404(Pedido.objects.select_related("cliente", "estado"), pk=pk)
    lineas_qs = pedido.lineas.select_related("producto").all()
    from decimal import Decimal
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
    # Obtener descuento e IVA
    descuento = Decimal(str(getattr(pedido, 'descuento', 0)))
    aplicar_iva = getattr(pedido, 'aplicar_iva', False)
    subtotal_con_descuento = subtotal * (Decimal("1") - descuento / Decimal("100")) if descuento else subtotal
    iva_multiplier = Decimal("1.21") if aplicar_iva else Decimal("1")
    monto_total = subtotal_con_descuento * iva_multiplier
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
            "iva_monto": (subtotal_con_descuento * Decimal("0.21")) if aplicar_iva else Decimal("0"),
            "monto_total": monto_total,
        },
    )


@require_perm('Pedidos', 'Editar')
def modificar_pedido(request, idPedido: int):
    """Permite modificar un pedido existente.

    Flujo:
    - Carga datos actuales en el formulario.
    - Al enviar, valida insumos disponibles.
    - Recalcula monto_total (precio x cantidad) y guarda.
    - Muestra mensajes de éxito o error.
    """
    from django.shortcuts import get_object_or_404
    from .models import LineaPedido

    pedido = get_object_or_404(Pedido.objects.select_related("cliente", "estado"), pk=idPedido)
    lineas_actuales = list(pedido.lineas.select_related('producto').all())

    if request.method == "POST":
        formset = LineaPedidoFormSet(request.POST, prefix="linea")
        form = ModificarPedidoForm(request.POST)
        if form.is_valid() and formset.is_valid():
            estado = form.cleaned_data["estado"]
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
            ok, faltantes = verificar_insumos_para_ajuste(old_lineas, new_lineas)
            if not ok:
                if faltantes:
                    try:
                        from insumos.models import Insumo
                        info = {i.idInsumo: (i.codigo, i.nombre)
                                for i in Insumo.objects.filter(idInsumo__in=faltantes.keys())}
                    except Exception:
                        info = {}
                    detalle = ", ".join([
                        f"{info.get(iid, ('-',f'Insumo {iid}'))[0]} - "
                        f"{info.get(iid, ('-',f'Insumo {iid}'))[1]}: faltan {falt:.2f}"
                        for iid, falt in faltantes.items()
                    ])
                    messages.error(request, f"No hay insumos suficientes: {detalle}")
                else:
                    messages.error(request, "No hay insumos suficientes.")
                precios = {p.pk: float(p.precio) for p in Producto.objects.all()}
                return render(request, "pedidos/modificar_pedido.html",
                              {"form": form, "formset": formset, "pedido": pedido, "precios": precios})

            # Calcular monto_total
            from decimal import Decimal
            monto_total = Decimal("0")
            for f in formset.cleaned_data:
                if f and not f.get('DELETE', False):
                    producto = f["producto"]
                    cantidad = f["cantidad"]
                    monto_total += (producto.precio or Decimal("0")) * cantidad

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
                pedido.monto_total = monto_total
                pedido.save()

            messages.success(request, "El pedido ha sido modificado correctamente.")
            return redirect("lista_pedidos")
        else:
            messages.error(request, "Revisá los datos del formulario")
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
        # Fecha de entrega: 10 días después de fecha_pedido si no está seteada
        from datetime import timedelta
        fecha_entrega_default = pedido.fecha_entrega or (pedido.fecha_pedido + timedelta(days=10))
        form = ModificarPedidoForm(initial={
            "estado": pedido.estado,
            "fecha_entrega": fecha_entrega_default,
        })

    precios = {p.pk: float(p.precio) for p in Producto.objects.all()}
    return render(request, "pedidos/modificar_pedido.html", {
        "form": form,
        "formset": formset,
        "pedido": pedido,
        "precios": precios,
        "estados": EstadoPedido.objects.all(),
        "productos": Producto.objects.filter(activo=True).order_by('nombreProducto'),
        "fecha_entrega": pedido.fecha_entrega.strftime('%Y-%m-%d') if pedido.fecha_entrega else '',
        "descuento_actual": int(pedido.descuento) if hasattr(pedido, 'descuento') else 0,
        "aplicar_iva_actual": pedido.aplicar_iva if hasattr(pedido, 'aplicar_iva') else False,
    })


@require_perm('Pedidos', 'Eliminar')
def eliminar_pedido(request, idPedido: int):
    """Eliminar Pedido con confirmación (POST). Visible para todos; el servidor valida permisos."""
    from django.shortcuts import get_object_or_404

    pedido = get_object_or_404(Pedido.objects.select_related("cliente", "estado"), pk=idPedido)
    if request.method == "POST":
        if not request.user.is_staff:
            messages.error(request, "No tenés permisos para eliminar pedidos.")
            return redirect("lista_pedidos")
        descripcion = f"Pedido {pedido.id} - {pedido.cliente}"
        from productos.models import ProductoInsumo
        # Obtener todas las líneas del pedido
        lineas = list(pedido.lineas.select_related('producto').all())
        # Verificar si alguna línea tiene receta definida
        hay_receta = any(
            ProductoInsumo.objects.filter(producto=linea.producto).exists()
            for linea in lineas
        )
        with transaction.atomic():
            if hay_receta:
                # Construir lista de tuplas (producto, cantidad) para reponer stock
                old_lineas = [(linea.producto, linea.cantidad) for linea in lineas]
                ajustar_insumos_por_diferencia(old_lineas, [])
            pedido.delete()
        messages.success(request, f"{descripcion} fue eliminado correctamente.")
        return redirect("lista_pedidos")
    return redirect("lista_pedidos")


@require_perm('Pedidos', 'Ver')
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
