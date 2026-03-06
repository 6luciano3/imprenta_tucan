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
    """
    Descuento (%) según el tier del cliente, usando la misma tabla de
    categorías que generar_ofertas_segmentadas() (core/ai_ml/ofertas.py).

      Premium    (score ≥ 90): 15 %
      Estratégico(score ≥ 60): 10 %
      Estándar   (score ≥ 30):  7 %
      Nuevo      (score  < 30):  5 %

    Unificar ambas vías en una sola función evita inconsistencias cuando
    los combos se crean desde la vista y desde la tarea Celery en paralelo.
    """
    try:
        from automatizacion.models import RankingCliente
        rc = RankingCliente.objects.filter(cliente=cliente).first()
        score = max(0.0, min(100.0, float(rc.score) if rc else 0.0))
    except Exception:
        score = 0.0
    # Deferred import para evitar circularidad a nivel de módulo
    from core.ai_ml.ofertas import descuento_por_score
    return descuento_por_score(score)

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

def _calcular_top_n(score, cliente_id):
    """
    Devuelve el número de productos que tendrá el combo según el rango del cliente.
    Usa cliente_id % 2 para alternar entre el valor bajo y alto del rango,
    asegurando variedad dentro del mismo tier sin ser aleatorio.
      Premium    (≥90): 5 ó 6 productos
      Estratégico (≥60): 4 ó 5 productos
      Estándar   (≥30): 3 ó 4 productos
      Nuevo       (<30): 2 ó 3 productos
    """
    parity = (cliente_id or 0) % 2
    if score >= 90:
        return 6 if parity else 5
    elif score >= 60:
        return 5 if parity else 4
    elif score >= 30:
        return 4 if parity else 3
    else:
        return 3 if parity else 2


def _armar_nombre_combo(productos_top):
    if not productos_top: return 'Combo Personalizado'
    nombres = [p['producto'].nombreProducto for p in productos_top[:2]]
    base = ' & '.join(nombres)
    return 'Combo ' + (base[:38] + '...' if len(base) > 40 else base)

def _productos_top_del_rango(score, excluir_cliente, top_n=4, offset=0):
    """
    Filtrado colaborativo: recoge un pool amplio (hasta 20) de los productos
    más pedidos por clientes del mismo rango, luego rota por `offset` (cliente.pk)
    para que cada cliente obtenga una selección distinta del mismo pool.
    """
    from automatizacion.models import RankingCliente
    from pedidos.models import LineaPedido
    from django.db.models import Count

    POOL_SIZE = 20  # cuántos candidatos distintos recogemos antes de rotar

    # Determinar límites del rango
    if score >= 90:
        score_min, score_max = 90, 200
    elif score >= 60:
        score_min, score_max = 60, 90
    elif score >= 30:
        score_min, score_max = 30, 60
    else:
        score_min, score_max = 0, 30

    # Clientes del mismo rango (excluido el propio)
    clientes_del_rango = (
        RankingCliente.objects
        .filter(score__gte=score_min, score__lt=score_max)
        .exclude(cliente=excluir_cliente)
        .values_list('cliente_id', flat=True)
    )

    # Productos que ya compró este cliente (para excluirlos del fallback)
    desde = timezone.now().date() - timedelta(days=180)
    ya_compro_ids = set(
        LineaPedido.objects
        .filter(pedido__cliente=excluir_cliente, pedido__fecha_pedido__gte=desde)
        .values_list('producto_id', flat=True)
    )

    qs = (
        LineaPedido.objects
        .filter(pedido__cliente_id__in=clientes_del_rango)
        .exclude(producto_id__in=ya_compro_ids)
        .values('producto')
        .annotate(veces=Count('id'))
        .order_by('-veces')
    )

    # Recolectar POOL_SIZE productos activos (sin detenernos en top_n)
    pool = []
    for item in qs[:POOL_SIZE * 3]:
        try:
            p = Producto.objects.get(pk=item['producto'], activo=True)
            pool.append({'producto': p, 'veces': item['veces'], 'cantidad_total': _cantidad_fallback(p)})
            if len(pool) >= POOL_SIZE:
                break
        except Producto.DoesNotExist:
            continue

    # Completar con los más pedidos globalmente si el pool es pequeño
    if len(pool) < top_n:
        ya_ids = {p['producto'].idProducto for p in pool}
        global_qs = (
            LineaPedido.objects
            .values('producto')
            .annotate(veces=Count('id'))
            .order_by('-veces')
        )
        for item in global_qs:
            if item['producto'] in ya_ids:
                continue
            try:
                p = Producto.objects.get(pk=item['producto'], activo=True)
                pool.append({'producto': p, 'veces': item['veces'], 'cantidad_total': _cantidad_fallback(p)})
                ya_ids.add(p.idProducto)
                if len(pool) >= POOL_SIZE:
                    break
            except Producto.DoesNotExist:
                continue

    if not pool:
        return []

    # Rotar el pool por offset para que cada cliente obtenga productos distintos
    rot = offset % len(pool)
    rotado = pool[rot:] + pool[:rot]
    return rotado[:top_n]


def _productos_por_precio(score, cliente_id, top_n=4):
    """
    Último fallback: seleccionà productos activos ordenados por precio.
    - Premium/Estratégico: precio descendente (productos de mayor valor)
    - Estándar/Nuevo: precio ascendente (productos de entrada)
    Usa (cliente_id % total) como offset para que clientes distintos
    del mismo rango reciban productos distintos.
    """
    if score >= 60:
        qs = list(Producto.objects.filter(activo=True).order_by('-precioUnitario'))
    else:
        qs = list(Producto.objects.filter(activo=True).order_by('precioUnitario'))
    if not qs:
        return []
    offset = (cliente_id or 0) % max(1, len(qs))
    # Rotar el pool para que el offset de cada cliente sea su punto de partida
    pool = (qs + qs)[offset:offset + top_n * 3]
    result = []
    seen = set()
    for p in pool:
        if p.idProducto not in seen:
            result.append({'producto': p, 'veces': 1, 'cantidad_total': _cantidad_fallback(p)})
            seen.add(p.idProducto)
            if len(result) >= top_n:
                break
    return result


def _cap_total_bruto(score):
    """
    Límite de precio bruto (antes del descuento) según el rango del cliente.
    Evita que clientes de score bajo reciban combos demasiado costosos.
      Nuevo      (<30): máx $10.000.000
      Estándar  (30-60): máx $40.000.000
      Estratégico(60-90): máx $80.000.000
      Premium    (≥90):  sin límite
    """
    if score < 30:
        return 10_000_000
    if score < 60:
        return 40_000_000
    if score < 90:
        return 80_000_000
    return None


def generar_combo_para_cliente(cliente):
    from automatizacion.models import RankingCliente
    rc = RankingCliente.objects.filter(cliente=cliente).first()
    score = float(rc.score) if rc else 0
    top_n = _calcular_top_n(score, cliente.pk)

    productos_top = _productos_mas_pedidos(cliente, top_n=top_n)
    if not productos_top:
        # Filtrado colaborativo: productos más pedidos por clientes del mismo rango
        productos_top = _productos_top_del_rango(score, cliente, top_n=top_n, offset=cliente.pk)
        if not productos_top:
            # Último recurso: por precio con offset único por cliente
            productos_top = _productos_por_precio(score, cliente.pk, top_n=top_n)
        if not productos_top:
            return None
    combo_existente = ComboOferta.objects.filter(
        cliente=cliente, fecha_inicio__gte=timezone.now() - timedelta(days=30)
    ).order_by('-fecha_inicio').first()
    if combo_existente:
        return combo_existente

    combo = ComboOferta.objects.create(
        cliente=cliente,
        nombre=_armar_nombre_combo(productos_top),
        descripcion='Oferta personalizada basada en tus productos mas pedidos.',
        descuento=_determinar_descuento(cliente),
        fecha_inicio=timezone.now(),
        fecha_fin=timezone.now() + timedelta(days=15),
    )

    # Calcular cantidades brutas
    cantidades = []
    for info in productos_top:
        cant = max(1, round(info['cantidad_total'] / max(info['veces'], 1)))
        cantidades.append((info['producto'], cant))

    # Aplicar cap: si el subtotal bruto supera el límite del tier, escalar
    # proporcionalmente todas las cantidades hacia abajo manteniendo mínimo 1
    cap = _cap_total_bruto(score)
    if cap is not None:
        subtotal_bruto = sum(
            float(p.precioUnitario or 0) * c for p, c in cantidades
        )
        if subtotal_bruto > cap:
            factor = cap / subtotal_bruto
            cantidades = [(p, max(1, round(c * factor))) for p, c in cantidades]

    for producto, cant in cantidades:
        ComboOfertaProducto.objects.create(combo=combo, producto=producto, cantidad=cant)
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
