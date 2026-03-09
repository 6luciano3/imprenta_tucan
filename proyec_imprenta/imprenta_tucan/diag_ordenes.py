"""Inspecciona las OrdenCompra que alimentan la proyección con valores más altos."""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()

from pedidos.models import OrdenCompra
from django.db.models import Sum

print("Top 20 OrdenCompra por cantidad (últimos 180 días):")
print(f"{'ID':>6}  {'insumo':>5}  {'cantidad':>10}  {'fecha':>20}  {'descripcion/notas'}")
print("-"*80)
from django.utils import timezone
from datetime import timedelta
hace_6m = timezone.now() - timedelta(days=180)
for oc in OrdenCompra.objects.filter(fecha_creacion__gte=hace_6m).order_by('-cantidad').select_related('insumo')[:20]:
    nombre = getattr(oc.insumo, 'nombre', '?') if oc.insumo else '?'
    print(f"{oc.id:>6}  {oc.insumo_id if oc.insumo_id else '':>5}  {oc.cantidad:>10}  {str(oc.fecha_creacion)[:19]:>20}  {nombre[:40]}")

print(f"\nTotal OC últimos 6m: {OrdenCompra.objects.filter(fecha_creacion__gte=hace_6m).count()}")
print(f"Total OC históricas: {OrdenCompra.objects.count()}")
