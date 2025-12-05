from automatizacion.models import ScoreProveedor
from proveedores.models import Proveedor
from django.utils import timezone
import random

# Eliminar todos los scores existentes
ScoreProveedor.objects.all().delete()
print('Todos los scores eliminados.')

# Crear scores de prueba para los primeros 10 proveedores existentes
proveedores = Proveedor.objects.all()[:10]
for proveedor in proveedores:
    score, created = ScoreProveedor.objects.update_or_create(
        proveedor=proveedor,
        defaults={
            'score': round(random.uniform(60, 100), 2),
            'actualizado': timezone.now()
        }
    )
    print(f"Score creado para Proveedor ID: {proveedor.id}, Nombre: {proveedor.nombre}, Score: {score.score}")
