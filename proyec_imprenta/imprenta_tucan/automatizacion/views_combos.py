# automatizacion/views_combos.py
from django.shortcuts import render
from django.http import HttpResponseBadRequest
from django.utils import timezone
from datetime import timedelta
from automatizacion.propuestas.models import ComboOferta, ComboOfertaProducto
from productos.models import Producto
from clientes.models import Cliente

def _productos_mas_pedidos(cliente, top_n=5, ventana_dias=180):
    desde = timezone.now().date() - timedelta(days=ventana_dias)
    from pedidos.models import LineaPedido
    lineas = (
        LineaPedido.objects
        .filter(pedido__cliente=cliente, pedido__fecha_pedido__gte=desde)
        .select_related('producto')
    )
    frecuencia = {}
    for linea in lineas:
        pid = linea.producto_id
        pid = linea.producto.idProducto
        if pid not in frecuencia:
            frecuencia[pid] = {'producto': linea.producto, 'veces': 0, 'cantidad_total': 0}
        frecuencia[pid]['veces'] += 1
        frecuencia[pid]['cantidad_total'] += int(linea.cantidad or 1)
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

def _cantidad_fallback(producto):
    """Cantidad realista por tipo de producto cuando no hay historial de pedidos."""
    nombre = (producto.nombreProducto or '').lower()
    if 'catálogo' in nombre or 'catalogo' in nombre:
        return 1000
    if 'revista' in nombre:
        return 2000
    if 'calendario' in nombre:
        return 50
    if any(k in nombre for k in ('caja', 'etiqueta')):
        return 200
    if 'libro' in nombre:
        return 500
    if 'manual' in nombre:
        return 50
    if 'carpeta' in nombre:
        return 100
    if 'tarjeta' in nombre:
        return 500
    if any(k in nombre for k in ('folleto', 'afiche', 'poster', 'póster')):
        return 100
    return 100  # default razonable

def _armar_nombre_combo(productos_top):
    if not productos_top: return 'Combo Personalizado'
    nombres = [p['producto'].nombreProducto for p in productos_top[:2]]
    base = ' & '.join(nombres)
    return 'Combo ' + (base[:38] + '...' if len(base) > 40 else base)

def generar_combo_para_cliente(cliente):
    productos_top = _productos_mas_pedidos(cliente)
    if not productos_top:
        # Productos distintos segun categoria del cliente
        from automatizacion.models import RankingCliente
        rc = RankingCliente.objects.filter(cliente=cliente).first()
        score = float(rc.score) if rc else 0

        if score >= 90:
            ids = [5, 7, 24, 37]   # Premium: Catalogo 40p, Revista 48p, Libro Tapa Dura, Poster
        elif score >= 60:
            ids = [8, 17, 39, 31]  # Estrategico: Carpeta Corp, Calendario, Manual, Caja Grande
        elif score >= 30:
            ids = [1, 12, 15, 27]  # Estandar: Folleto A4, Tarjeta Premium, Afiche A2, Cuaderno
        else:
            ids = [11, 2, 28, 19]  # Nuevo: Tarjeta Color, Folleto A5, Etiquetas, Bloc A5

        top_global = list(Producto.objects.filter(idProducto__in=ids, activo=True))
        if not top_global:
            top_global = list(Producto.objects.filter(activo=True).order_by('-idProducto')[:4])
        if not top_global: return None
        productos_top = [{'producto': p, 'veces': 1, 'cantidad_total': _cantidad_fallback(p)} for p in top_global]
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

def _fmt_num(n):
    """Formatea un número con separador de miles (punto), sin decimales."""
    return f'{int(round(n)):,}'.replace(',', '.')

def _serializar_combo(combo):
    items = []
    subtotal = 0.0
    for cop in combo.comboofertaproducto_set.select_related('producto').all():
        precio = float(cop.precio_unitario if hasattr(cop, 'precio_unitario') and cop.precio_unitario else cop.producto.precioUnitario or 0)
        cant = int(cop.cantidad or 1)
        sub = precio * cant
        subtotal += sub
        items.append({
            'nombre': cop.producto.nombreProducto,
            'cantidad': _fmt_num(cant),
            'precio_unitario': _fmt_num(precio),
            'subtotal': _fmt_num(sub),
        })
    descuento = float(combo.descuento or 0)
    descuento_valor = subtotal * descuento / 100
    return {
        'nombre': combo.nombre, 'descripcion': combo.descripcion, 'descuento': descuento,
        'items': items,
        'subtotal': _fmt_num(subtotal),
        'descuento_valor': _fmt_num(descuento_valor),
        'total_final': _fmt_num(subtotal - descuento_valor),
        'aceptada': combo.aceptada, 'rechazada': combo.rechazada,
        'enviada': combo.enviada, 'fecha_fin': combo.fecha_fin,
    }

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
