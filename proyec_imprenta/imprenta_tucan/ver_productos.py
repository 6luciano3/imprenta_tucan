from productos.models import Producto
prods = Producto.objects.filter(activo=True).order_by("idProducto")
print(f"Total productos activos: {prods.count()}")
for p in prods:
    print(f"ID {p.idProducto} | {p.nombreProducto}")
