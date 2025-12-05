from proveedores.models import Proveedor
from automatizacion.models import ScoreProveedor
from django.utils import timezone

# Crear proveedores de prueba
proveedores = []
for i in range(1, 6):
    proveedor, created = Proveedor.objects.get_or_create(
        nombre=f"Proveedor Test {i}",
        cuit=f"20-1234567{i}-1",
        email=f"proveedor{i}@test.com",
        telefono=f"381-555-000{i}",
        direccion=f"Calle Falsa {i}00",
        rubro="Papel",
        activo=True
    )
    proveedores.append(proveedor)

# Crear scores de prueba
for idx, proveedor in enumerate(proveedores):
    ScoreProveedor.objects.update_or_create(
        proveedor=proveedor,
        defaults={
            'score': 100 - idx * 10,
            'actualizado': timezone.now()
        }
    )

print("Proveedores y scores de prueba creados correctamente.")
