import django, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()

from automatizacion.models import OfertaPropuesta, RankingCliente
from automatizacion.propuestas.models import ComboOferta
from django.utils import timezone

ahora = timezone.now()
periodo = f'{ahora.year}-{str(ahora.month).zfill(2)}'

OfertaPropuesta.objects.filter(periodo=periodo).delete()
ComboOferta.objects.all().delete()

from automatizacion.tasks import tarea_generar_ofertas
print(tarea_generar_ofertas())
print()

from automatizacion.views_combos import _serializar_combo

print(f"  {'Score':>6}  {'Desc%':>6}  {'Total Final':>14}  Cliente")
print(f"  {'-'*6}  {'-'*6}  {'-'*14}  {'-'*25}")
for rc in RankingCliente.objects.order_by('-score')[:20]:
    combo = ComboOferta.objects.filter(cliente=rc.cliente).order_by('-fecha_inicio').first()
    if not combo:
        continue
    data = _serializar_combo(combo)
    sc = float(rc.score)
    desc = data['descuento']
    total = data['total_final']
    nombre = rc.cliente.nombre[:25]
    print(f"  {sc:>6.1f}  {desc:>5.1f}%  ${total:>13}  {nombre}")
