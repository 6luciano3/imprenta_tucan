import django, os, sys
sys.path.insert(0, ".")
os.environ["DJANGO_SETTINGS_MODULE"] = "impre_tucan.settings"
django.setup()

from insumos.models import Insumo
from proveedores.models import Proveedor

prov = Proveedor.objects.first()

# Insumos base para imprenta
insumos_data = [
    # (codigo, nombre, categoria, tipo, stock_inicial)
    # PAPELES
    ("PAP-ILU-115", "Papel Ilustracion 115g", "Papel", "directo", 10000),
    ("PAP-ILU-130", "Papel Ilustracion 130g", "Papel", "directo", 10000),
    ("PAP-ILU-150", "Papel Ilustracion 150g", "Papel", "directo", 10000),
    ("PAP-OBR-080", "Papel Obra 80g",         "Papel", "directo", 5000),
    ("PAP-AUT-CON", "Papel Autocopiativo Blanco 75g", "Papel", "directo", 3000),
    # CARTULINAS
    ("CAR-ILU-250", "Cartulina Ilustracion 250g", "Cartulina", "directo", 5000),
    ("CAR-ILU-300", "Cartulina Ilustracion 300g", "Cartulina", "directo", 5000),
    ("CAR-ILU-350", "Cartulina Ilustracion 350g", "Cartulina", "directo", 5000),
    ("CAR-GRI-150", "Carton Gris 1.5mm",          "Carton",    "directo", 2000),
    ("CAR-GRI-200", "Carton Gris 2mm",             "Carton",    "directo", 2000),
    # TINTAS
    ("TIN-CYAN",    "Tinta Cyan",    "Tinta", "directo", 50),
    ("TIN-MAGE",    "Tinta Magenta", "Tinta", "directo", 50),
    ("TIN-AMAR",    "Tinta Amarilla","Tinta", "directo", 50),
    ("TIN-NEGR",    "Tinta Negra",   "Tinta", "directo", 100),
    # PLANCHAS
    ("PLA-ALU-STD", "Plancha Aluminio Estandar", "Plancha", "directo", 500),
    # TERMINACIONES
    ("BAR-UV-LIQ",  "Barniz UV Liquido",     "Barniz",   "directo", 20),
    ("LAM-MAT-32",  "Laminado Mate 32mic",   "Laminado", "directo", 500),
    ("LAM-BRI-32",  "Laminado Brillante 32mic", "Laminado", "directo", 500),
    # ENCUADERNACION
    ("ENC-ESP-MET", "Espiral Metalico",      "Encuadernacion", "directo", 1000),
    ("ENC-GRA-IND", "Grampas Industriales",  "Encuadernacion", "directo", 5000),
    ("ENC-HOT-MEL", "Hot Melt Pegamento",    "Encuadernacion", "directo", 20),
    ("ENC-ADH-BLO", "Adhesivo Bloc",         "Encuadernacion", "directo", 10),
]

creados = 0
existentes = 0
for codigo, nombre, categoria, tipo, stock in insumos_data:
    obj, created = Insumo.objects.get_or_create(
        codigo=codigo,
        defaults={
            "nombre": nombre,
            "categoria": categoria,
            "tipo": tipo,
            "stock": stock,
            "precio": 0,
            "precio_unitario": 0,
            "proveedor": prov,
        }
    )
    if created:
        creados += 1
        print(f"  CREADO: {codigo} | {nombre}")
    else:
        existentes += 1

print(f"\nResumen: {creados} creados, {existentes} ya existian")
print(f"Total insumos ahora: {Insumo.objects.count()}")
