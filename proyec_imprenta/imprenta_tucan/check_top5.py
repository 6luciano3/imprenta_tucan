import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()

from automatizacion.models import ScoreProveedor

print('=== TOP 10 proveedores por score ===')
scores = ScoreProveedor.objects.filter(
    proveedor__activo=True
).exclude(proveedor__email__endswith='.local'
).exclude(proveedor__email=''
).exclude(proveedor__email__isnull=True
).select_related('proveedor').order_by('-score')

for i, s in enumerate(scores[:10]):
    marca = ' <-- TOP 5' if i < 5 else ''
    print(str(i+1) + '. ' + str(s.proveedor.nombre) + ' | score=' + str(s.score) + ' | ' + str(s.proveedor.email) + marca)
