import django, os, sys
sys.path.insert(0, ".")
os.environ["DJANGO_SETTINGS_MODULE"] = "impre_tucan.settings"
django.setup()

from productos.models import Producto, ParametroProducto, RecetaDinamica, LineaReceta
from insumos.models import Insumo

# Obtener insumos por codigo
def ins(codigo):
    return Insumo.objects.get(codigo=codigo)

# Parametros tecnicos por producto_id
# (R, M, C, F, Formas, ancho, alto, gramaje, At, Ct, barniz, Cb, laminado)
PARAMS = {
    # Folletos
    1:  dict(R=8,  M=0.05, C=4, F=2, Formas=1, gramaje=150, At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Folleto A4 Color
    2:  dict(R=8,  M=0.05, C=1, F=1, Formas=1, gramaje=130, At=0.0312, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Folleto A5 B/N
    3:  dict(R=8,  M=0.05, C=4, F=2, Formas=1, gramaje=150, At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Folleto Triptico A4
    32: dict(R=4,  M=0.05, C=4, F=2, Formas=1, gramaje=150, At=0.04,   Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Folleto Cuadrado 20x20
    33: dict(R=8,  M=0.05, C=4, F=2, Formas=1, gramaje=150, At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Diptico A4
    # Catalogos
    4:  dict(R=8,  M=0.05, C=4, F=2, Formas=3, gramaje=130, At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=True),   # Catalogo 20 pag
    5:  dict(R=8,  M=0.05, C=4, F=2, Formas=5, gramaje=130, At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=True),   # Catalogo 40 pag
    # Revistas
    6:  dict(R=8,  M=0.05, C=4, F=2, Formas=4, gramaje=115, At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Revista 32 pag
    7:  dict(R=8,  M=0.05, C=4, F=2, Formas=6, gramaje=115, At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Revista 48 pag
    # Carpetas
    8:  dict(R=2,  M=0.05, C=4, F=1, Formas=1, gramaje=350, At=0.09,   Ct=1.5, tiene_barniz=False, tiene_laminado=True),   # Carpeta con Solapas
    9:  dict(R=2,  M=0.05, C=4, F=1, Formas=1, gramaje=300, At=0.09,   Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Carpeta Simple
    10: dict(R=2,  M=0.05, C=4, F=1, Formas=1, gramaje=350, At=0.09,   Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Carpeta con Bolsillo
    36: dict(R=2,  M=0.05, C=4, F=1, Formas=1, gramaje=350, At=0.09,   Ct=1.5, tiene_barniz=True,  Cb=2.0, tiene_laminado=False),  # Carpeta Laca UV
    # Tarjetas
    11: dict(R=20, M=0.05, C=4, F=2, Formas=1, gramaje=300, At=0.0054, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Tarjeta Color
    12: dict(R=20, M=0.05, C=4, F=2, Formas=1, gramaje=350, At=0.0054, Ct=1.5, tiene_barniz=False, tiene_laminado=True),   # Tarjeta Premium
    13: dict(R=8,  M=0.05, C=4, F=2, Formas=1, gramaje=250, At=0.0315, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Invitacion
    # Afiches
    14: dict(R=2,  M=0.05, C=4, F=1, Formas=1, gramaje=130, At=0.0594, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Afiche A3
    15: dict(R=1,  M=0.05, C=4, F=1, Formas=1, gramaje=130, At=0.1188, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Afiche A2
    16: dict(R=1,  M=0.05, C=4, F=1, Formas=1, gramaje=130, At=0.2376, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Afiche A1
    37: dict(R=1,  M=0.05, C=4, F=1, Formas=1, gramaje=130, At=0.70,   Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Poster 70x100
    # Calendarios
    17: dict(R=2,  M=0.05, C=4, F=2, Formas=2, gramaje=150, At=0.0594, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Calendario Pared A3
    18: dict(R=4,  M=0.05, C=4, F=2, Formas=2, gramaje=150, At=0.03,   Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Calendario Escritorio
    38: dict(R=16, M=0.05, C=4, F=2, Formas=1, gramaje=150, At=0.008,  Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Calendario Bolsillo
    # Blocs
    19: dict(R=8,  M=0.05, C=1, F=1, Formas=1, gramaje=80,  At=0.0312, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Bloc A5
    20: dict(R=4,  M=0.05, C=1, F=1, Formas=1, gramaje=80,  At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Bloc A4
    # Talonarios
    21: dict(R=4,  M=0.05, C=1, F=1, Formas=1, gramaje=75,  At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Talonario Facturas
    22: dict(R=4,  M=0.05, C=1, F=1, Formas=1, gramaje=75,  At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Talonario Remitos
    23: dict(R=4,  M=0.05, C=1, F=1, Formas=1, gramaje=75,  At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Talonario Presupuestos
    # Libros
    24: dict(R=8,  M=0.05, C=4, F=2, Formas=7, gramaje=130, At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=True),   # Libro Tapa Dura 100p
    25: dict(R=8,  M=0.05, C=4, F=2, Formas=13,gramaje=130, At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Libro Tapa Blanda 200p
    # Cuadernos
    26: dict(R=8,  M=0.05, C=4, F=2, Formas=4, gramaje=80,  At=0.0312, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Cuaderno A5 Espiral
    27: dict(R=4,  M=0.05, C=4, F=2, Formas=4, gramaje=80,  At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Cuaderno Corp A4
    # Etiquetas
    28: dict(R=16, M=0.05, C=4, F=1, Formas=1, gramaje=90,  At=0.01,   Ct=1.5, tiene_barniz=True,  Cb=2.0, tiene_laminado=False),  # Etiquetas 10x10
    29: dict(R=32, M=0.05, C=4, F=1, Formas=1, gramaje=90,  At=0.0025, Ct=1.5, tiene_barniz=True,  Cb=2.0, tiene_laminado=False),  # Etiquetas Rollo 5x5
    # Cajas
    30: dict(R=4,  M=0.05, C=4, F=1, Formas=1, gramaje=350, At=0.04,   Ct=1.5, tiene_barniz=True,  Cb=2.0, tiene_laminado=False),  # Caja Pequena
    31: dict(R=2,  M=0.05, C=4, F=1, Formas=1, gramaje=350, At=0.09,   Ct=1.5, tiene_barniz=True,  Cb=2.0, tiene_laminado=False),  # Caja Grande
    # Otros
    34: dict(R=4,  M=0.05, C=1, F=1, Formas=1, gramaje=80,  At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Membrete A4
    35: dict(R=4,  M=0.05, C=1, F=1, Formas=1, gramaje=120, At=0.0312, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Sobres C5
    39: dict(R=8,  M=0.05, C=1, F=2, Formas=4, gramaje=80,  At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Manual 60p
    40: dict(R=4,  M=0.05, C=4, F=2, Formas=1, gramaje=300, At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=True),   # Menu Plastificado
    41: dict(R=4,  M=0.05, C=4, F=1, Formas=1, gramaje=130, At=0.0624, Ct=1.5, tiene_barniz=False, tiene_laminado=False),  # Producto Ejemplo
}

# Papel por producto_id
PAPEL = {
    1: "PAP-ILU-150", 2: "PAP-ILU-130", 3: "PAP-ILU-150",
    4: "PAP-ILU-130", 5: "PAP-ILU-130", 6: "PAP-ILU-115",
    7: "PAP-ILU-115", 8: "CAR-ILU-350", 9: "CAR-ILU-300",
    10: "CAR-ILU-350", 11: "CAR-ILU-300", 12: "CAR-ILU-350",
    13: "CAR-ILU-250", 14: "PAP-ILU-130", 15: "PAP-ILU-130",
    16: "PAP-ILU-130", 17: "PAP-ILU-150", 18: "PAP-ILU-150",
    19: "PAP-OBR-080", 20: "PAP-OBR-080", 21: "PAP-AUT-CON",
    22: "PAP-AUT-CON", 23: "PAP-AUT-CON", 24: "PAP-ILU-130",
    25: "PAP-ILU-130", 26: "PAP-OBR-080", 27: "PAP-OBR-080",
    28: "CAR-ILU-300", 29: "CAR-ILU-300", 30: "CAR-ILU-350",
    31: "CAR-ILU-350", 32: "PAP-ILU-150", 33: "PAP-ILU-150",
    34: "PAP-OBR-080", 35: "PAP-OBR-080", 36: "CAR-ILU-350",
    37: "PAP-ILU-130", 38: "PAP-ILU-150", 39: "PAP-OBR-080",
    40: "CAR-ILU-300", 41: "PAP-ILU-130",
}

# Tinta por cantidad de colores
def tinta_cod(C):
    return "TIN-NEGR" if C == 1 else "TIN-CYAN"

creadas = 0
for prod_id, params in PARAMS.items():
    try:
        producto = Producto.objects.get(idProducto=prod_id)
    except Producto.DoesNotExist:
        print(f"  SKIP: producto {prod_id} no existe")
        continue

    # Crear/actualizar ParametroProducto
    pp, _ = ParametroProducto.objects.update_or_create(
        producto=producto,
        defaults={
            "R": params["R"],
            "M": params["M"],
            "C": params["C"],
            "F": params["F"],
            "Formas": params["Formas"],
            "gramaje": params["gramaje"],
            "At": params["At"],
            "Ct": params["Ct"],
            "tiene_barniz": params.get("tiene_barniz", False),
            "Cb": params.get("Cb", 0),
            "tiene_laminado": params.get("tiene_laminado", False),
        }
    )

    # Crear RecetaDinamica
    receta, _ = RecetaDinamica.objects.update_or_create(
        producto=producto,
        defaults={"activo": True, "version": 1}
    )
    # Limpiar lineas anteriores
    receta.lineas.all().delete()

    # Linea PAPEL
    papel_cod = PAPEL.get(prod_id, "PAP-ILU-130")
    LineaReceta.objects.create(
        receta=receta, insumo=ins(papel_cod),
        tipo="papel", orden=1
    )

    # Linea TINTA
    tinta = ins(tinta_cod(params["C"]))
    LineaReceta.objects.create(
        receta=receta, insumo=tinta,
        tipo="tinta", orden=2
    )

    # Linea PLANCHA
    LineaReceta.objects.create(
        receta=receta, insumo=ins("PLA-ALU-STD"),
        tipo="plancha", orden=3
    )

    # Linea BARNIZ (si aplica)
    if params.get("tiene_barniz"):
        LineaReceta.objects.create(
            receta=receta, insumo=ins("BAR-UV-LIQ"),
            tipo="barniz", orden=4
        )

    # Linea LAMINADO (si aplica)
    if params.get("tiene_laminado"):
        LineaReceta.objects.create(
            receta=receta, insumo=ins("LAM-MAT-32"),
            tipo="laminado", orden=5
        )

    creadas += 1
    print(f"  OK: {producto.nombreProducto}")

print(f"\nTotal recetas cargadas: {creadas}")
