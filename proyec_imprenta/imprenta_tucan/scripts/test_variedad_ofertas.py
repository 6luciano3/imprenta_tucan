import django, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()

from automatizacion.models import OfertaPropuesta
from automatizacion.propuestas.models import ComboOferta, ComboOfertaProducto
from django.utils import timezone

ahora = timezone.now()
periodo = f'{ahora.year}-{str(ahora.month).zfill(2)}'

# Borrar ofertas y combos del periodo para forzar recálculo completo
OfertaPropuesta.objects.filter(periodo=periodo).delete()
ComboOferta.objects.all().delete()
print(f'Período {periodo}: ofertas y combos eliminados.')

from automatizacion.tasks import tarea_generar_ofertas
resultado = tarea_generar_ofertas()
print(resultado)
print()

for cat in ['Premium', 'Estrategico', 'Estandar', 'Nuevo']:
    ofertas = OfertaPropuesta.objects.filter(periodo=periodo, parametros__categoria=cat)
    total = ofertas.count()
    # Contar productos por combo usando parametros['combo_id']
    conteo = {}
    for o in ofertas:
        combo_id = o.parametros.get('combo_id') if o.parametros else None
        if not combo_id:
            continue
        n = ComboOfertaProducto.objects.filter(combo_id=combo_id).count()
        conteo[n] = conteo.get(n, 0) + 1
    distribucion = ', '.join(f'{n} prods: {v} combos' for n, v in sorted(conteo.items()))
    print(f'  {cat:12s} ({total:3d} clientes): {distribucion or "sin combos"}')

