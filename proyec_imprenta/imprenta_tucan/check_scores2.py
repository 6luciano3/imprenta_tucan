import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()

from automatizacion.models import ScoreProveedor

# Ver campos del modelo
s = ScoreProveedor.objects.first()
print('Campos ScoreProveedor: ' + str([f.name for f in s._meta.fields]))
print()

# Ver proveedores con email real y sus scores
from automatizacion.models import ScoreProveedor
scores = ScoreProveedor.objects.filter(
    proveedor__activo=True
).exclude(proveedor__email__endswith='.local'
).exclude(proveedor__email=''
).exclude(proveedor__email__isnull=True
).select_related('proveedor').order_by('-id')[:10]

for s in scores:
    print(str(s.proveedor.nombre) + ' | ' + str(s.proveedor.email))

print()
# Ver por que no se generaron propuestas - revisar tarea
from automatizacion.models import CompraPropuesta
from insumos.models import Insumo
from configuracion.models import Parametro

stock_min = int(Parametro.get('STOCK_MINIMO_GLOBAL', 20))
insumos_bajos = Insumo.objects.filter(stock__lte=stock_min, activo=True)
print('Insumos bajo stock: ' + str(insumos_bajos.count()))

bloqueados = 0
for insumo in insumos_bajos:
    ya = CompraPropuesta.objects.filter(insumo=insumo, consulta_stock__isnull=False).exists()
    if ya:
        bloqueados += 1
print('Insumos bloqueados por propuesta existente: ' + str(bloqueados))
print('Insumos libres para generar: ' + str(insumos_bajos.count() - bloqueados))
