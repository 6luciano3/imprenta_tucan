from automatizacion.models import ScoreProveedor
from proveedores.models import Proveedor

print('Proveedores existentes:')
for p in Proveedor.objects.all():
    print(f"ID: {p.id}, Nombre: {p.nombre}")

print('\nScores existentes:')
for s in ScoreProveedor.objects.all():
    print(f"ID: {s.id}, Proveedor ID: {s.proveedor_id}, Score: {s.score}")
