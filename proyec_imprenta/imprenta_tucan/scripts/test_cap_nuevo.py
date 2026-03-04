import django, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()

from automatizacion.models import RankingCliente
from automatizacion.propuestas.models import ComboOferta
from automatizacion.views_combos import _serializar_combo, _cap_total_bruto

CAP = 10_000_000

print("=== Clientes Nuevo (score < 30) ===")
print(f"  {'Score':>6}  {'Desc%':>6}  {'Bruto':>14}  {'Total Final':>14}  {'Cap':>12}  OK?  Cliente")
print(f"  {'-'*6}  {'-'*6}  {'-'*14}  {'-'*14}  {'-'*12}  ---  {'-'*20}")

errores = 0
for rc in RankingCliente.objects.filter(score__lt=30).order_by('score'):
    combo = ComboOferta.objects.filter(cliente=rc.cliente).order_by('-fecha_inicio').first()
    if not combo:
        continue
    # Calcular bruto y total con descuento manualmente
    bruto = 0.0
    for cop in combo.comboofertaproducto_set.select_related('producto').all():
        precio = float(cop.producto.precioUnitario or 0)
        cant = int(cop.cantidad or 1)
        bruto += precio * cant
    desc = float(combo.descuento or 0)
    total_final = bruto * (1 - desc / 100)
    cap_tier = _cap_total_bruto(float(rc.score))
    cumple = 'OK' if (cap_tier is None or total_final <= cap_tier) else 'FALLA'
    if cumple == 'FALLA':
        errores += 1
    cap_str = f"${cap_tier:,.0f}".replace(',', '.') if cap_tier else 'sin límite'
    print(f"  {float(rc.score):>6.1f}  {desc:>5.1f}%  ${bruto:>13,.0f}  ${total_final:>13,.0f}  {cap_str:>12}  {cumple}  {rc.cliente.nombre[:20]}")

print()
print(f"Errores (superan el cap): {errores}/{RankingCliente.objects.filter(score__lt=30).count()}")
