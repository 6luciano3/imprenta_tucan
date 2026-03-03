import django, os, sys
sys.path.insert(0, ".")
os.environ["DJANGO_SETTINGS_MODULE"] = "impre_tucan.settings"
django.setup()

from insumos.models import Insumo

precios = {
    "PAP-ILU-115": 620,
    "PAP-ILU-130": 720,
    "PAP-ILU-150": 850,
    "PAP-OBR-080": 380,
    "PAP-AUT-CON": 450,
    "CAR-ILU-250": 900,
    "CAR-ILU-300": 1050,
    "CAR-ILU-350": 1200,
    "CAR-GRI-150": 800,
    "CAR-GRI-200": 950,
    "TIN-CYAN":  18000,
    "TIN-MAGE":  18000,
    "TIN-AMAR":  18000,
    "TIN-NEGR":  12000,
    "PLA-ALU-STD": 3500,
    "BAR-UV-LIQ":  15000,
    "LAM-MAT-32":   800,
    "LAM-BRI-32":   750,
    "ENC-ESP-MET":  120,
    "ENC-GRA-IND":    8,
    "ENC-HOT-MEL": 9000,
    "ENC-ADH-BLO": 7000,
}

actualizados = 0
for codigo, precio in precios.items():
    try:
        insumo = Insumo.objects.get(codigo=codigo)
        insumo.precio = precio
        insumo.precio_unitario = precio
        insumo.save()
        print(f"  OK: {insumo.nombre} -> ${precio:,}")
        actualizados += 1
    except Insumo.DoesNotExist:
        print(f"  SKIP: {codigo} no encontrado")

print(f"\nTotal actualizados: {actualizados}")
