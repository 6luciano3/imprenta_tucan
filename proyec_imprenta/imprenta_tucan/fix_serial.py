import pathlib
p = pathlib.Path('automatizacion/views_combos.py')
txt = p.read_text(encoding='utf-8')

# Corregir _serializar_combo para usar idProducto en ComboOfertaProducto
old_serial = '''def _serializar_combo(combo):
    items = []
    subtotal = 0.0
    for cop in combo.comboofertaproducto_set.select_related('producto').all():
        precio = float(cop.producto.precioUnitario or 0)
        cant = int(cop.cantidad or 1)
        sub = precio * cant
        subtotal += sub
        items.append({'nombre': cop.producto.nombreProducto, 'cantidad': cant, 'precio_unitario': precio, 'subtotal': sub})'''

new_serial = '''def _serializar_combo(combo):
    items = []
    subtotal = 0.0
    for cop in combo.comboofertaproducto_set.select_related('producto').all():
        precio = float(cop.precio_unitario if hasattr(cop, 'precio_unitario') and cop.precio_unitario else cop.producto.precioUnitario or 0)
        cant = int(cop.cantidad or 1)
        sub = precio * cant
        subtotal += sub
        items.append({'nombre': cop.producto.nombreProducto, 'cantidad': cant, 'precio_unitario': precio, 'subtotal': sub})'''

if old_serial in txt:
    txt = txt.replace(old_serial, new_serial)
    print('_serializar_combo actualizado OK')
else:
    print('(serializar ya estaba OK)')

p.write_text(txt, encoding='utf-8')

# Ahora verificar precios reales en la DB
from productos.models import Producto
print('\n=== Precios de productos activos ===')
for prod in Producto.objects.filter(activo=True).order_by('-idProducto')[:6]:
    print(f'  {prod.nombreProducto}: ')

# Ver si LineaPedido tiene datos
from pedidos.models import LineaPedido
total = LineaPedido.objects.count()
print(f'\nTotal LineaPedido en DB: {total}')
if total > 0:
    lp = LineaPedido.objects.select_related('producto','pedido__cliente').first()
    print(f'  Ejemplo: {lp.pedido.cliente} -> {lp.producto.nombreProducto} x{lp.cantidad} precio_linea={lp.precio_unitario}')
