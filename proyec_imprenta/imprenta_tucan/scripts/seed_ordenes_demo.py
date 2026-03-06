"""
Script: seed_ordenes_demo.py
Genera órdenes de compra demo para todos los proveedores activos,
con estados y fechas variados dentro de los últimos 90 días.
Uso: python manage.py shell < scripts/seed_ordenes_demo.py
  o: python scripts/seed_ordenes_demo.py (desde manage.py shell)
"""
import os
import sys
import random
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()

from django.utils import timezone
from django.db import connection
from proveedores.models import Proveedor
from insumos.models import Insumo
from pedidos.models import OrdenCompra

random.seed(42)
ahora = timezone.now()
creados = 0

proveedores = list(Proveedor.objects.filter(activo=True))
print(f'Proveedores activos: {len(proveedores)}')

for proveedor in proveedores:
    insumos = list(Insumo.objects.filter(proveedor=proveedor)[:3])
    if not insumos:
        continue

    n_ordenes = random.randint(5, 14)
    for _ in range(n_ordenes):
        insumo = random.choice(insumos)
        dias_atras = random.randint(1, 85)
        fecha = ahora - timedelta(days=dias_atras)

        r = random.random()
        if r < 0.65:
            estado = 'confirmada'
        elif r < 0.80:
            estado = 'rechazada'
        else:
            estado = 'sugerida'

        dias_resp = random.randint(1, 15) if estado in ('confirmada', 'rechazada') else None
        fecha_respuesta = fecha + timedelta(days=dias_resp) if dias_resp else None
        cantidad = random.choice([500, 1000, 2000, 5000])

        oc = OrdenCompra(
            insumo=insumo,
            cantidad=cantidad,
            proveedor=proveedor,
            estado=estado,
            comentario='[demo]',
            fecha_respuesta=fecha_respuesta,
        )
        # Evitar que save() sobreescriba fecha_respuesta con timezone.now()
        oc.skip_auto_fecha_respuesta = True
        oc.save()

        # Actualizar fecha_creacion (auto_now_add no acepta valor manual)
        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE pedidos_ordencompra SET fecha_creacion=%s, fecha_respuesta=%s WHERE id=%s',
                [fecha.isoformat(), fecha_respuesta.isoformat() if fecha_respuesta else None, oc.pk]
            )
        creados += 1

print(f'Creadas {creados} ordenes de compra demo para {len(proveedores)} proveedores')

# Recalcular scores con los nuevos datos
from automatizacion.tasks import tarea_recalcular_scores_proveedores
result = tarea_recalcular_scores_proveedores()
print(f'Recálculo: {result}')

# Mostrar top 5
from automatizacion.models import ScoreProveedor
print('\nTop 5 proveedores:')
for s in ScoreProveedor.objects.select_related('proveedor').order_by('-score')[:5]:
    print(f'  {s.proveedor.nombre[:35]:<35} score={s.score}')
