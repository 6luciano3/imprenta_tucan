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
    
    ultimos_insumos = Insumo.objects.filter(activo=True).exclude(precio=0).exclude(precio__isnull=True).order_by('-idInsumo')[:10]
    
    for insumo in ultimos_insumos:
        if insumo.precio:
            insumo.precio_mas_10 = insumo.precio * Decimal('1.10')
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
            queryset = queryset.filter(precio__isnull=False, precio__gt=0)
        
        from decimal import Decimal
        from django.db import transaction
        
        factor = Decimal('1') + Decimal(str(porcentaje)) / Decimal('100')
        
        insumos_actualizados = 0
        errores = []
        
        with transaction.atomic():
            for insumo in queryset:
                try:
                    if insumo.precio:
                        nuevo_precio = (insumo.precio * factor).quantize(Decimal('0.01'))
                        if nuevo_precio < 0:
                            errores.append(f"{insumo.nombre}: precio no puede ser negativo")
                            continue
                        insumo.precio = nuevo_precio
                        insumo.save(update_fields=['precio'])
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
