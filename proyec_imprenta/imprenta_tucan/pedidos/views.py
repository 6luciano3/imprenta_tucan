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
from .utils import (
    verificar_insumos_disponibles,
    verificar_insumos_para_lineas,
    descontar_insumos_para_lineas,
    verificar_insumos_para_ajuste,
    ajustar_insumos_por_diferencia,
)
from productos.models import Producto


def lista_pedidos(request):
    """Lista unificada con búsqueda, orden y paginación para Pedidos."""
    query = (request.GET.get("q", "") or request.GET.get("criterio", "")).strip()
    order_by = request.GET.get("order_by", "id")
    direction = request.GET.get("direction", "desc")

    valid_order_fields = [
        "id", "cliente__nombre", "cliente__apellido", "producto__nombreProducto",
        "fecha_pedido", "fecha_entrega", "estado__nombre", "monto_total"
    ]
    if order_by not in valid_order_fields:
        order_by = "id"

    qs = Pedido.objects.select_related("cliente", "producto", "estado")

    if query:
        if query.isdigit():
            qs = qs.filter(Q(id=int(query)) |
                           Q(cliente__nombre__icontains=query) |
                           Q(cliente__apellido__icontains=query) |
                           Q(cliente__razon_social__icontains=query) |
                           Q(producto__nombreProducto__icontains=query) |
                           Q(estado__nombre__icontains=query))
        else:
            qs = qs.filter(
                Q(cliente__nombre__icontains=query) |
                Q(cliente__apellido__icontains=query) |
                Q(cliente__razon_social__icontains=query) |
                Q(producto__nombreProducto__icontains=query) |
                Q(estado__nombre__icontains=query)
            )

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
                        f"{info.get(iid, ('-', f'Insumo {iid}'))[0]} - {info.get(iid, ('-', f'Insumo {iid}'))[1]}: faltan {falt:.2f}"
                        for iid, falt in faltantes.items()
                    ])
                    messages.warning(request, f"No hay insumos suficientes: {detalle}. El pedido se guardó igualmente.")
                else:
                    messages.warning(request, "No hay insumos suficientes para las cantidades solicitadas. El pedido se guardó igualmente.")

            subtotal = Decimal("0")
            # Descontar stock y crear pedidos en una transacción
            with transaction.atomic():
                descontar_insumos_para_lineas([(p, c) for (p, c, _e) in lineas])
                for producto, cantidad, especificaciones in lineas:
                    line_total = (producto.precio or Decimal("0")) * cantidad
                    subtotal += line_total
                    monto_total = line_total * iva_multiplier
                    Pedido.objects.create(
                        cliente=cliente,
                        producto=producto,
                        fecha_entrega=fecha_entrega,
                        cantidad=cantidad,
                        especificaciones=especificaciones,
                        monto_total=monto_total,
                        estado=estado_pendiente,
                    )

            total_con_iva = subtotal * iva_multiplier
            cant_lineas = len([f for f in formset if not f.cleaned_data.get('DELETE')
                              and f.cleaned_data.get('producto') and f.cleaned_data.get('cantidad')])
            if aplicar_iva:
                messages.success(
                    request, f"Se registraron {cant_lineas} productos. Subtotal: ${subtotal:.2f} | Total c/IVA (21%): ${total_con_iva:.2f}")
            else:
                messages.success(request, f"Se registraron {cant_lineas} productos. Subtotal: ${subtotal:.2f}")
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
    # Productos para calculadora en Alta (con unidad de medida)
    productos_calculadora = list(
        Producto.objects.filter(activo=True)
        .order_by('nombreProducto')
        .values('idProducto', 'nombreProducto', 'unidadMedida__abreviatura', 'unidadMedida__nombreUnidad')
    )
    precios = {p.pk: float(p.precio) for p in Producto.objects.all()}
    return render(
        request,
        "pedidos/alta_pedido.html",
        {"header_form": header_form, "formset": formset, "fecha_pedido_hoy": fecha_pedido_hoy,
            "precios": precios, "productos_calculadora": productos_calculadora},
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

    pedido = get_object_or_404(Pedido.objects.select_related("producto"), pk=idPedido)
    producto_id = body.get("producto")
    cantidad = int(body.get("cantidad") or 0)

    if not producto_id or cantidad <= 0:
        # Si no hay datos, no bloquear
        return JsonResponse({"ok": True, "faltantes": []})

    try:
        prod = Producto.objects.get(pk=producto_id)
    except Producto.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Producto inválido"}, status=400)

    old_lineas = [(pedido.producto, pedido.cantidad)]
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


def buscar_pedido(request):
    cliente_context = None
    pedidos = None
    if request.method == "POST":
        form = SeleccionarClienteForm(request.POST)
        if form.is_valid():
            cliente = form.cleaned_data["cliente"]
            cliente_context = cliente
            pedidos = (
                Pedido.objects.select_related("producto", "estado")
                .filter(cliente=cliente)
                .order_by("-id")
            )
            if not pedidos.exists():
                from django.contrib import messages
                messages.error(request, "El cliente no tiene pedidos registrados")
    else:
        form = SeleccionarClienteForm()

    return render(request, "pedidos/buscar_pedido.html", {"form": form, "pedidos": pedidos, "cliente": cliente_context})


def detalle_pedido(request, pk: int):
    from django.shortcuts import get_object_or_404

    pedido = get_object_or_404(Pedido.objects.select_related("cliente", "producto", "estado"), pk=pk)
    # Calcular insumos requeridos según receta (si existe)
    insumos_requeridos = []
    try:
        from productos.models import ProductoInsumo
        receta = list(
            ProductoInsumo.objects.filter(producto=pedido.producto).select_related("insumo")
        )
        for r in receta:
            requerido = float(r.cantidad_por_unidad) * float(pedido.cantidad or 0)
            stock = float(getattr(r.insumo, "stock", 0))
            faltan = max(0.0, requerido - stock)
            insumos_requeridos.append(
                {
                    "id": getattr(r.insumo, "idInsumo", None),
                    "codigo": getattr(r.insumo, "codigo", "-"),
                    "nombre": getattr(r.insumo, "nombre", "Insumo"),
                    "requerido": requerido,
                    "stock": stock,
                    "faltan": faltan,
                }
            )
    except Exception:
        pass

    return render(
        request,
        "pedidos/detalle_pedido.html",
        {"pedido": pedido, "insumos_requeridos": insumos_requeridos},
    )


def modificar_pedido(request, idPedido: int):
    """Permite modificar un pedido existente.

    Flujo:
    - Carga datos actuales en el formulario.
    - Al enviar, valida insumos disponibles.
    - Recalcula monto_total (precio x cantidad) y guarda.
    - Muestra mensajes de éxito o error.
    """
    from django.shortcuts import get_object_or_404

    pedido = get_object_or_404(Pedido.objects.select_related("cliente", "producto", "estado"), pk=idPedido)

    if request.method == "POST":
        form = ModificarPedidoForm(request.POST)
        if form.is_valid():
            producto = form.cleaned_data["producto"]
            estado = form.cleaned_data["estado"]
            fecha_entrega = form.cleaned_data["fecha_entrega"]
            cantidad = form.cleaned_data["cantidad"]
            especificaciones = form.cleaned_data["especificaciones"]

            # Validación de insumos considerando el ajuste neto respecto al pedido anterior
            old_lineas = [(pedido.producto, pedido.cantidad)]
            new_lineas = [(producto, cantidad)]
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
                        f"{info.get(iid, ('-', f'Insumo {iid}'))
                           [0]} - {info.get(iid, ('-', f'Insumo {iid}'))[1]}: faltan {falt:.2f}"
                        for iid, falt in faltantes.items()
                    ])
                    messages.error(request, f"No hay insumos suficientes: {detalle}")
                else:
                    messages.error(request, "No hay insumos suficientes para la cantidad solicitada.")
                # Re-render con el mismo formulario y contexto
                precios = {p.pk: float(p.precio) for p in Producto.objects.all()}
                return render(
                    request,
                    "pedidos/modificar_pedido.html",
                    {"form": form, "pedido": pedido, "precios": precios},
                )

            # Calcular monto total
            monto_total = (producto.precio or 0) * cantidad

            # Ajustar stock por diferencia y persistir cambios de forma atómica
            with transaction.atomic():
                ajustar_insumos_por_diferencia(old_lineas, new_lineas)

                pedido.producto = producto
                pedido.estado = estado
                pedido.fecha_entrega = fecha_entrega
                pedido.cantidad = cantidad
                pedido.especificaciones = especificaciones
                pedido.monto_total = monto_total
                pedido.save()

            messages.success(request, "El pedido ha sido modificado correctamente.")
            return redirect("lista_pedidos")
        else:
            messages.error(request, "Revisá los datos del formulario")
    else:
        form = ModificarPedidoForm(
            initial={
                "producto": pedido.producto,
                "estado": pedido.estado,
                "fecha_entrega": pedido.fecha_entrega,
                "cantidad": pedido.cantidad,
                "especificaciones": pedido.especificaciones,
            }
        )

    precios = {p.pk: float(p.precio) for p in Producto.objects.all()}
    return render(
        request,
        "pedidos/modificar_pedido.html",
        {
            "form": form,
            "pedido": pedido,
            "precios": precios,
        },
    )


def eliminar_pedido(request, idPedido: int):
    """Eliminar Pedido con confirmación (POST). Visible para todos; el servidor valida permisos."""
    from django.shortcuts import get_object_or_404

    pedido = get_object_or_404(Pedido.objects.select_related("producto"), pk=idPedido)
    if request.method == "POST":
        if not request.user.is_staff:
            messages.error(request, "No tenés permisos para eliminar pedidos.")
            return redirect("lista_pedidos")
        descripcion = f"Pedido {pedido.id} - {pedido.cliente}"
        # Reponer stock por la diferencia (de estado actual a 'nada') si hay recetas
        from productos.models import ProductoInsumo
        hay_receta = ProductoInsumo.objects.filter(producto=pedido.producto).exists()
        with transaction.atomic():
            if hay_receta:
                # old_lineas: lo que consumió el pedido; new_lineas vacío => repone
                ajustar_insumos_por_diferencia([(pedido.producto, pedido.cantidad)], [])
            pedido.delete()
        messages.success(request, f"{descripcion} fue eliminado correctamente.")
        return redirect("lista_pedidos")
    return redirect("lista_pedidos")
