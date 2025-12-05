from automatizacion.models import ScoreProveedor
from proveedores.models import Proveedor
from django.utils import timezone
import random

# Crear scores de prueba para todos los proveedores existentes
for proveedor in Proveedor.objects.all():
    ScoreProveedor.objects.update_or_create(
        proveedor=proveedor,
        defaults={
            'score': round(random.uniform(60, 100), 2),
            'actualizado': timezone.now()
        }
    )
print('Scores de prueba creados para todos los proveedores existentes.')
