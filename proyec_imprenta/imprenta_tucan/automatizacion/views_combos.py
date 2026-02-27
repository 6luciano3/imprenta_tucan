# automatizacion/views_combos.py
from django.shortcuts import render
from django.http import HttpResponseBadRequest
from django.utils import timezone
from datetime import timedelta
from .propuestas.models import ComboOferta, ComboOfertaProducto
from productos.models import Producto
from clientes.models import Cliente
from pedidos.models import Pedido

def _productos_mas_pedidos(cliente, top_n=5, ventana_dias=180):
    desde = timezone.now().date() - timedelta(days=ventana_dias)
    pedidos = Pedido.objects.filter(cliente=cliente, fecha_pedido__gte=desde).select_related('producto').order_by('-fecha_pedido')
    frecuencia = {}
    for p in pedidos:
        if p.producto_id not in frecuencia:
            frecuencia[p.producto_id] = {'producto': p.producto, 'veces': 0, 'cantidad_total': 0}
        frecuencia[p.producto_id]['veces'] += 1
        frecuencia[p.producto_id]['cantidad_total'] += int(p.cantidad or 1)
    return sorted(frecuencia.values(), key=lambda x: x['veces'], reverse=True)[:top_n]

def _determinar_descuento(cliente):
    try:
        from automatizacion.models import RankingCliente
        rc = RankingCliente.objects.filter(cliente=cliente).first()
        score = float(rc.score) if rc else 0.0
    except Exception:
        score = 0.0
    if score >= 80: return 15
    elif score >= 60: return 10
    elif score >= 30: return 7
    else: return 5

def _armar_nombre_combo(productos_top):
    if not productos_top: return 'Combo Personalizado'
    nombres = [p['producto'].nombreProducto for p in productos_top[:2]]
    base = ' & '.join(nombres)
    return 'Combo ' + (base[:38] + '...' if len(base) > 40 else base)

def generar_combo_para_cliente(cliente):
    productos_top = _productos_mas_pedidos(cliente)
    if not productos_top:
        top_global = list(Producto.objects.order_by('-id')[:4])
        if not top_global: return None
        productos_top = [{'producto': p, 'veces': 1, 'cantidad_total': 2} for p in top_global]
    combo_existente = ComboOferta.objects.filter(cliente=cliente, fecha_inicio__gte=timezone.now() - timedelta(days=30)).order_by('-fecha_inicio').first()
    if combo_existente: return combo_existente
    combo = ComboOferta.objects.create(
        cliente=cliente,
        nombre=_armar_nombre_combo(productos_top),
        descripcion='Oferta personalizada basada en tus productos mas pedidos.',
        descuento=_determinar_descuento(cliente),
        fecha_inicio=timezone.now(),
        fecha_fin=timezone.now() + timedelta(days=15),
    )
    for info in productos_top:
        cant = max(1, round(info['cantidad_total'] / max(info['veces'], 1)))
        ComboOfertaProducto.objects.create(combo=combo, producto=info['producto'], cantidad=cant)
    return combo

def _serializar_combo(combo):
    items = []
    subtotal = 0.0
    for cop in combo.comboofertaproducto_set.select_related('producto').all():
        precio = float(cop.producto.precioUnitario or 0)
        cant = int(cop.cantidad or 1)
        sub = precio * cant
        subtotal += sub
        items.append({'nombre': cop.producto.nombreProducto, 'cantidad': cant, 'precio_unitario': precio, 'subtotal': sub})
    descuento = float(combo.descuento or 0)
    descuento_valor = subtotal * descuento / 100
    return {'nombre': combo.nombre, 'descripcion': combo.descripcion, 'descuento': descuento,
            'items': items, 'subtotal': subtotal, 'descuento_valor': descuento_valor,
            'total_final': subtotal - descuento_valor, 'aceptada': combo.aceptada,
            'rechazada': combo.rechazada, 'enviada': combo.enviada, 'fecha_fin': combo.fecha_fin}

def lista_combos_oferta(request):
    is_popup = request.GET.get('popup') == '1'
    cliente_id = request.GET.get('cliente_id')
    if is_popup:
        if not cliente_id: return HttpResponseBadRequest('Falta cliente_id')
        try:
            cliente = Cliente.objects.get(pk=cliente_id)
        except Cliente.DoesNotExist:
            return render(request, 'automatizacion/combo_oferta_popup.html', {'combos': []})
        combo = generar_combo_para_cliente(cliente)
        return render(request, 'automatizacion/combo_oferta_popup.html', {'combos': [_serializar_combo(combo)] if combo else []})
    combos_qs = ComboOferta.objects.select_related('cliente').order_by('-fecha_inicio')
    return render(request, 'automatizacion/lista_combos_oferta.html', {'combos': [_serializar_combo(c) for c in combos_qs]})
