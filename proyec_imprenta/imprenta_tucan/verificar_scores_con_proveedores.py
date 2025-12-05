from automatizacion.models import ScoreProveedor

print('Scores y proveedores asociados:')
for s in ScoreProveedor.objects.all():
    try:
        proveedor = s.proveedor
        print(f"Score ID: {s.id}, Proveedor ID: {proveedor.id}, Nombre: {proveedor.nombre}, Score: {s.score}")
    except Exception as e:
        print(f"Score ID: {s.id}, Proveedor no encontrado (ID: {s.proveedor_id}), Error: {e}")
