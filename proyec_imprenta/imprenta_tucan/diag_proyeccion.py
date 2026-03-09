"""Diagnóstico: muestra la fuente y valores reales que alimentan api_proyeccion_demanda."""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()

from insumos.models import Insumo, ProyeccionInsumo, ConsumoRealInsumo, predecir_demanda_media_movil
from pedidos.models import OrdenCompra
from django.utils import timezone
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from datetime import timedelta

hoy = timezone.now()
periodo_actual = hoy.strftime('%Y-%m')
hace_6m = hoy - timedelta(days=180)

nombres_buscar = [
    'Laminado Mate', 'Papel Ilustración', 'Barniz Acrílico',
    'Papel Vegetal', 'Tinta Pantone 185', 'Tinta Pantone Reflex',
    'Tinta Negra', 'Barniz Mate', 'Barniz Brillante', 'Tinta Cyan',
]

for nombre in nombres_buscar:
    insumo = Insumo.objects.filter(nombre__icontains=nombre.split()[0]).first()
    if not insumo:
        continue
    print(f"\n{'='*60}")
    print(f"INSUMO: {insumo.nombre} (id={insumo.idInsumo})")
    print(f"  stock={insumo.stock}, cantidad_catalogo={insumo.cantidad}, stock_minimo_manual={insumo.stock_minimo_manual}")

    # Fuente 1
    proy = ProyeccionInsumo.objects.filter(insumo=insumo, periodo=periodo_actual).first()
    print(f"  F1 ProyeccionInsumo [{periodo_actual}]: {proy.cantidad_proyectada if proy else 'NINGUNA'}")

    # Fuente 2
    consumos = list(ConsumoRealInsumo.objects.filter(insumo=insumo).order_by('-periodo')[:6]
                    .values_list('periodo', 'cantidad_consumida'))
    print(f"  F2 ConsumoRealInsumo (últimos 6 registros): {consumos}")
    mm = predecir_demanda_media_movil(insumo, periodo_actual, meses=3)
    print(f"     → media_movil_ponderada(meses=3): {mm}")

    # Fuente 3
    total_ordenes = OrdenCompra.objects.filter(insumo=insumo, fecha_creacion__gte=hace_6m).aggregate(t=Sum('cantidad'))['t']
    meses_act = (OrdenCompra.objects.filter(insumo=insumo, fecha_creacion__gte=hace_6m)
                 .annotate(mes=TruncMonth('fecha_creacion')).values('mes').distinct().count())
    print(f"  F3 OrdenCompra últimos 6m: total={total_ordenes}, meses_activos={meses_act}, promedio={round(total_ordenes/meses_act,1) if total_ordenes and meses_act else 'N/A'}")
