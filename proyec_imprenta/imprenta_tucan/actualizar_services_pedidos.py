filepath = r"pedidos/services.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

nuevo_calcular = """
def calcular_consumo_producto(producto, cantidad: int) -> dict:
    \"\"\"Calcula consumo usando RecetaDinamica si existe, sino fallback a BOM estatico.\"\"\"
    from decimal import Decimal
    from collections import defaultdict
    req = defaultdict(Decimal)
    if not producto or not cantidad:
        return dict(req)

    # Intentar RecetaDinamica primero
    try:
        receta = producto.receta_dinamica
        if receta and receta.activo:
            return receta.calcular(cantidad)
    except Exception:
        pass

    # Fallback: BOM estatico (ProductoInsumo)
    from productos.models import ProductoInsumo
    import math
    for r in ProductoInsumo.objects.filter(producto=producto).select_related("insumo"):
        nombre = (r.insumo.nombre or "").lower()
        if "plancha" in nombre:
            req[r.insumo_id] += Decimal(r.cantidad_por_unidad)
        else:
            req[r.insumo_id] += Decimal(r.cantidad_por_unidad) * Decimal(cantidad)
    return dict(req)
"""

# Reemplazar la funcion existente
import re
patron = r"def calcular_consumo_producto\(.*?\n(?=def |\Z)"
nuevo = nuevo_calcular.strip() + "\n\n\n"
resultado = re.sub(patron, nuevo, content, flags=re.DOTALL)

if resultado == content:
    print("ADVERTENCIA: no se encontro la funcion original, agregando al inicio")
    resultado = nuevo_calcular + "\n" + content

with open(filepath, "w", encoding="utf-8") as f:
    f.write(resultado)
print("services.py actualizado OK")
