import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyec_imprenta.imprenta_tucan.settings_custom')
import sys
from decimal import Decimal
# Asegura que la raíz del proyecto esté en el path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyec_imprenta.imprenta_tucan.settings_custom')
import django

def asignar_formula_a_productos():
    from productos.models import Producto
    from configuracion.models import Formula
    productos = Producto.objects.all()
    total = 0
    asignados = 0
    for p in productos:
        total += 1
        formula = None
        # Prioridad: papel_insumo, luego tinta_insumo
        if getattr(p, 'papel_insumo_id', None):
            formula = Formula.objects.filter(insumo_id=p.papel_insumo_id, activo=True).first()
        if not formula and getattr(p, 'tinta_insumo_id', None):
            formula = Formula.objects.filter(insumo_id=p.tinta_insumo_id, activo=True).first()
        if formula and (p.formula_id != formula.id):
            p.formula = formula
            p.save()
            asignados += 1
            print(f"[✓] {p.nombreProducto} -> fórmula: {formula.nombre}")
        else:
            print(f"[ ] {p.nombreProducto} (sin fórmula asignada o ya asignada)")
    print(f"\nResumen: {asignados} fórmulas asignadas de {total} productos.")
        else:
