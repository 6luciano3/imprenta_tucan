import os
import sys
import django

sys.path.insert(0, 'proyec_imprenta/imprenta_tucan')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()

from decimal import Decimal

print("=== TEST: Validación de límites ===\n")

# Simular las validaciones del view
def validar_porcentaje(porcentaje_str):
    porcentaje_str = porcentaje_str.replace(',', '.')
    try:
        porcentaje = float(porcentaje_str)
    except ValueError:
        return "ERROR: Porcentaje inválido"
    
    if porcentaje < -30:
        return f"ERROR: El porcentaje no puede ser menor a -30% (recibido: {porcentaje}%)"
    elif porcentaje > 100:
        return f"ERROR: El porcentaje no puede ser mayor a 100% (recibido: {porcentaje}%)"
    
    return f"OK: Porcentaje válido: {porcentaje}%"

# Tests
tests = [
    "10",
    "-10",
    "100",
    "-30",
    "150",
    "-50",
    "0",
    "50.5",
    "-25.5",
]

for test in tests:
    resultado = validar_porcentaje(test)
    print(f"{test:>10}% -> {resultado}")

print("\n=== TEST: Cálculo de precios ===\n")

# Simular cálculo
def calcular_precio(precio, porcentaje):
    factor = Decimal('1') + Decimal(str(porcentaje)) / Decimal('100')
    nuevo_precio = (precio * factor).quantize(Decimal('0.01'))
    return nuevo_precio

precio_base = Decimal('1000.00')
porcentajes = [10, -10, 50, -30, 100]

for p in porcentajes:
    nuevo = calcular_precio(precio_base, p)
    print(f"{precio_base} + {p}% = {nuevo}")

print("\n=== Tests completados ===")
