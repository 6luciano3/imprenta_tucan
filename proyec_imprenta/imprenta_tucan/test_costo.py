import django, os, sys
sys.path.insert(0, ".")
os.environ["DJANGO_SETTINGS_MODULE"] = "impre_tucan.settings"
django.setup()

from productos.models import Producto
from pedidos.services import calcular_consumo_producto
from insumos.models import Insumo

def costo_directo(producto, cantidad):
    consumo = calcular_consumo_producto(producto, cantidad)
    total = 0
    print(f"\nProducto: {producto.nombreProducto} | Q: {cantidad}")
    print(f"{'Insumo':<35} {'Cant':>10} {'P.Unit':>10} {'Subtotal':>12}")
    print("-" * 70)
    for insumo_id, qty in consumo.items():
        insumo = Insumo.objects.get(idInsumo=insumo_id)
        precio = float(insumo.precio_unitario or 0)
        subtotal = float(qty) * precio
        total += subtotal
        print(f"  {insumo.nombre:<33} {float(qty):>10.3f} {precio:>10,.0f} {subtotal:>12,.0f}")
    print("-" * 70)
    print(f"  {'COSTO DIRECTO TOTAL':<33} {'':>10} {'':>10} {total:>12,.0f}")
    costo_unit = total / cantidad if cantidad else 0
    print(f"  {'COSTO UNITARIO':<33} {'':>10} {'':>10} {costo_unit:>12,.0f}")
    return total

# Carpeta Corporativa x100
p1 = Producto.objects.get(idProducto=8)
costo_directo(p1, 100)

# Manual de Usuario x30
p2 = Producto.objects.get(idProducto=39)
costo_directo(p2, 30)

# Caja Plegadiza Grande x200
p3 = Producto.objects.get(idProducto=31)
costo_directo(p3, 200)
