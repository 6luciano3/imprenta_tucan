import django, os, sys
sys.path.insert(0, ".")
os.environ["DJANGO_SETTINGS_MODULE"] = "impre_tucan.settings"
django.setup()

from productos.models import Producto
from pedidos.services import calcular_consumo_producto
from insumos.models import Insumo

# Probar con Carpeta Corporativa con Solapas (ID 8) - cantidad 100
producto = Producto.objects.get(idProducto=8)
cantidad = 100

print(f"Producto: {producto.nombreProducto}")
print(f"Cantidad: {cantidad}")
print()

consumo = calcular_consumo_producto(producto, cantidad)

print("Insumos requeridos:")
for insumo_id, qty in consumo.items():
    insumo = Insumo.objects.get(idInsumo=insumo_id)
    print(f"  {insumo.nombre:35s} -> {qty:10.3f} {insumo.categoria}")

print()
# Probar con Manual de Usuario (ID 39) - cantidad 30
producto2 = Producto.objects.get(idProducto=39)
consumo2 = calcular_consumo_producto(producto2, 30)
print(f"Producto: {producto2.nombreProducto} | Cantidad: 30")
for insumo_id, qty in consumo2.items():
    insumo = Insumo.objects.get(idInsumo=insumo_id)
    print(f"  {insumo.nombre:35s} -> {qty:10.3f} {insumo.categoria}")
