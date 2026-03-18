from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import OrdenCompra, DetalleOrdenCompra, Remito, DetalleRemito, EstadoCompra
from .forms import OrdenCompraForm, DetalleOrdenCompraFormSet, RemitoForm, DetalleRemitoFormSet


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
    ordenes = OrdenCompra.objects.select_related("proveedor", "estado", "usuario").prefetch_related("detalles__insumo")
    return render(request, "compras/lista_ordenes.html", {"ordenes": ordenes})


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


@login_required
def nuevo_remito(request):
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
                    DetalleRemito.objects.create(remito=remito, insumo=insumo, cantidad=cantidad)
                    insumo.stock = (insumo.stock or 0) + cantidad
                    insumo.save(update_fields=["stock", "updated_at"])
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
        form = RemitoForm(initial={"fecha": timezone.now().date()})
        formset = DetalleRemitoFormSet(prefix="detalles")
    return render(request, "compras/nuevo_remito.html", {"form": form, "formset": formset})


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
