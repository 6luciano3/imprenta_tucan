from productos.models import CategoriaProducto, TipoProducto, UnidadMedida, Producto
import os
import django
from decimal import Decimal
from django.db import transaction

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()


def parse_precio(valor):
    s = str(valor).strip()
    # eliminar separadores de miles comunes
    s = s.replace('.', '').replace(',', '')
    if not s:
        return Decimal('0')
    return Decimal(s)


def abreviar(texto, maxlen=10):
    t = (texto or '').strip()
    # Usa primeras palabras y recorta a maxlen
    return t[:maxlen] if len(t) > maxlen else t


datos = [
    {"nombre": "Folleto A4 Color", "desc": "Folleto doble faz en papel ilustración 150g",
        "precio": "280", "categoria": "Folletos", "tipo": "Publicitario", "unidad": "Tamaño: 21×29,7 cm"},
    {"nombre": "Folleto A5 Blanco y Negro", "desc": "Folleto económico en papel obra 80g",
        "precio": "150", "categoria": "Folletos", "tipo": "Publicitario", "unidad": "Tamaño: 14,8×21 cm"},
    {"nombre": "Folleto Tríptico A4", "desc": "Folleto plegado en tres cuerpos, full color", "precio": "320",
        "categoria": "Folletos", "tipo": "Publicitario", "unidad": "Tamaño: 29,7×21 cm abierto"},
    {"nombre": "Catálogo Corporativo 20 pág.", "desc": "Catálogo institucional con tapas laminadas",
        "precio": "2,800", "categoria": "Catálogos", "tipo": "Editorial", "unidad": "20 páginas"},
    {"nombre": "Catálogo de Productos 40 pág.", "desc": "Encuadernado con lomo cuadrado",
        "precio": "4,200", "categoria": "Catálogos", "tipo": "Editorial", "unidad": "40 páginas"},
    {"nombre": "Revista Mensual 32 pág.", "desc": "Revista full color en papel ilustración 115g",
        "precio": "3,500", "categoria": "Revistas", "tipo": "Editorial", "unidad": "32 páginas"},
    {"nombre": "Revista Institucional 48 pág.", "desc": "Impresión offset a color, lomo cuadrado",
        "precio": "4,800", "categoria": "Revistas", "tipo": "Editorial", "unidad": "48 páginas"},
    {"nombre": "Carpeta Corporativa con Solapas", "desc": "Carpeta impresa en cartulina 300g con laminado mate",
        "precio": "850", "categoria": "Carpetas", "tipo": "Corporativo", "unidad": "Tamaño: 22×31 cm"},
    {"nombre": "Carpeta Simple sin Laminado", "desc": "Carpeta en cartulina ilustración 300g",
        "precio": "600", "categoria": "Carpetas", "tipo": "Corporativo", "unidad": "Tamaño: 22×31 cm"},
    {"nombre": "Carpeta con Bolsillo Interno", "desc": "Carpeta full color troquelada",
        "precio": "1,100", "categoria": "Carpetas", "tipo": "Corporativo", "unidad": "Tamaño: 22×31 cm"},
    {"nombre": "Tarjeta Personal Color", "desc": "Tarjeta doble faz en cartulina 300g",
        "precio": "90", "categoria": "Tarjetas", "tipo": "Corporativo", "unidad": "Tamaño: 9×5 cm"},
    {"nombre": "Tarjeta Personal Premium Laminada", "desc": "Tarjeta con laminado mate y barniz UV sectorizado",
        "precio": "150", "categoria": "Tarjetas", "tipo": "Corporativo", "unidad": "Tamaño: 9×5 cm"},
    {"nombre": "Tarjeta de Invitación 15x21 cm", "desc": "Invitación color en papel texturado 250g",
        "precio": "180", "categoria": "Tarjetas", "tipo": "Social", "unidad": "Tamaño: 15×21 cm"},
    {"nombre": "Afiche A3 Color", "desc": "Cartel promocional en papel ilustración brillante",
        "precio": "250", "categoria": "Afiches", "tipo": "Publicitario", "unidad": "Tamaño: 29,7×42 cm"},
    {"nombre": "Afiche A2 Color", "desc": "Cartel para vidrieras o eventos", "precio": "350",
        "categoria": "Afiches", "tipo": "Publicitario", "unidad": "Tamaño: 42×59,4 cm"},
    {"nombre": "Afiche A1 Color", "desc": "Impresión offset gran formato", "precio": "480",
        "categoria": "Afiches", "tipo": "Publicitario", "unidad": "Tamaño: 59,4×84,1 cm"},
    {"nombre": "Calendario de Pared A3", "desc": "Calendario mensual personalizado", "precio": "1,200",
        "categoria": "Calendarios", "tipo": "Promocional", "unidad": "Tamaño: 29,7×42 cm"},
    {"nombre": "Calendario de Escritorio Triangular", "desc": "Calendario con espiral metálico",
        "precio": "1,000", "categoria": "Calendarios", "tipo": "Promocional", "unidad": "Tamaño: 21×10 cm"},
    {"nombre": "Bloc de Notas A5 50 hojas", "desc": "Bloc personalizado con logo de empresa",
        "precio": "750", "categoria": "Papelería", "tipo": "Oficina", "unidad": "50 hojas A5 (14,8×21 cm)"},
    {"nombre": "Bloc de Notas A4 100 hojas", "desc": "Bloc corporativo en papel obra 80g", "precio": "1,200",
        "categoria": "Papelería", "tipo": "Oficina", "unidad": "100 hojas A4 (21×29,7 cm)"},
    {"nombre": "Talonario de Facturas", "desc": "Numerado, duplicado, papel autocopiativo",
        "precio": "900", "categoria": "Formularios", "tipo": "Comercial", "unidad": "50 juegos"},
    {"nombre": "Talonario de Remitos", "desc": "Autocopiativo duplicado personalizado",
        "precio": "950", "categoria": "Formularios", "tipo": "Comercial", "unidad": "50 juegos"},
    {"nombre": "Talonario de Presupuestos", "desc": "Impreso con logo y numeración",
        "precio": "950", "categoria": "Formularios", "tipo": "Comercial", "unidad": "50 juegos"},
    {"nombre": "Libro Tapa Dura 100 pág.", "desc": "Encuadernado con tapa rígida laminada",
        "precio": "6,500", "categoria": "Libros", "tipo": "Editorial", "unidad": "100 páginas"},
    {"nombre": "Libro Tapa Blanda 200 pág.", "desc": "Impreso en papel obra 80g",
        "precio": "4,800", "categoria": "Libros", "tipo": "Editorial", "unidad": "200 páginas"},
    {"nombre": "Cuaderno A5 con Espiral", "desc": "Cuaderno personalizado 80 hojas rayadas", "precio": "1,400",
        "categoria": "Cuadernos", "tipo": "Papelería", "unidad": "80 hojas A5 (14,8×21 cm)"},
    {"nombre": "Cuaderno Corporativo A4", "desc": "Cuaderno institucional con logo", "precio": "1,800",
        "categoria": "Cuadernos", "tipo": "Papelería", "unidad": "100 hojas A4 (21×29,7 cm)"},
    {"nombre": "Etiquetas Adhesivas 10x10 cm", "desc": "Etiquetas troqueladas impresas full color",
        "precio": "30", "categoria": "Etiquetas", "tipo": "Promocional", "unidad": "Tamaño: 10×10 cm"},
    {"nombre": "Etiquetas Rollo 5x5 cm", "desc": "Etiquetas impresas en papel autoadhesivo",
        "precio": "25", "categoria": "Etiquetas", "tipo": "Promocional", "unidad": "Tamaño: 5×5 cm"},
    {"nombre": "Caja Plegadiza Pequeña", "desc": "Caja troquelada para cosmética",
        "precio": "850", "categoria": "Packaging", "tipo": "Comercial", "unidad": "10×10×5 cm"},
    {"nombre": "Caja Plegadiza Grande", "desc": "Caja personalizada para productos premium",
        "precio": "1,200", "categoria": "Packaging", "tipo": "Comercial", "unidad": "25×20×10 cm"},
    {"nombre": "Folleto Cuadrado 20x20 cm", "desc": "Folleto moderno full color", "precio": "300",
        "categoria": "Folletos", "tipo": "Publicitario", "unidad": "Tamaño: 20×20 cm"},
    {"nombre": "Díptico A4 Color", "desc": "Folleto plegado en dos cuerpos", "precio": "260",
        "categoria": "Folletos", "tipo": "Publicitario", "unidad": "Tamaño: 29,7×21 cm abierto"},
    {"nombre": "Membrete A4 Corporativo", "desc": "Hoja institucional en papel obra 90g",
        "precio": "200", "categoria": "Papelería", "tipo": "Oficina", "unidad": "Tamaño: 21×29,7 cm"},
    {"nombre": "Sobres Corporativos C5", "desc": "Sobre con logo impreso en offset", "precio": "180",
        "categoria": "Papelería", "tipo": "Oficina", "unidad": "Tamaño: 16,2×22,9 cm"},
    {"nombre": "Carpetas con Laca UV Parcial", "desc": "Carpeta premium con brillo sectorizado",
        "precio": "1,300", "categoria": "Carpetas", "tipo": "Corporativo", "unidad": "Tamaño: 22×31 cm"},
    {"nombre": "Poster Gigante 70x100 cm", "desc": "Impresión offset alta resolución", "precio": "650",
        "categoria": "Posters", "tipo": "Publicitario", "unidad": "Tamaño: 70×100 cm"},
    {"nombre": "Calendario de Bolsillo", "desc": "Calendario personalizable a color", "precio": "250",
        "categoria": "Calendarios", "tipo": "Promocional", "unidad": "Tamaño: 9×6 cm"},
    {"nombre": "Manual de Usuario 60 pág.", "desc": "Encuadernado con grapas metálicas",
        "precio": "3,200", "categoria": "Manuales", "tipo": "Técnico", "unidad": "60 páginas"},
    {"nombre": "Menú de Restaurante Plastificado", "desc": "Menú full color con laminado brillante",
        "precio": "900", "categoria": "Menús", "tipo": "Comercial", "unidad": "Tamaño: 21×29,7 cm"},
]


@transaction.atomic
def cargar_productos():
    creados = 0
    actualizados = 0

    for row in datos:
        cat, _ = CategoriaProducto.objects.get_or_create(
            nombreCategoria=row["categoria"], defaults={"descripcion": row["categoria"]}
        )
        tipo, _ = TipoProducto.objects.get_or_create(
            nombreTipoProducto=row["tipo"], defaults={"descripcion": row["tipo"]}
        )
        uni, _ = UnidadMedida.objects.get_or_create(
            nombreUnidad=row["unidad"],
            defaults={"abreviatura": abreviar(row["unidad"])},
        )

        precio = parse_precio(row["precio"])

        prod, created = Producto.objects.get_or_create(
            nombreProducto=row["nombre"],
            defaults={
                "descripcion": row["desc"],
                "precioUnitario": precio,
                "categoriaProducto": cat,
                "tipoProducto": tipo,
                "unidadMedida": uni,
            },
        )

        if not created:
            # Actualizar datos principales por si cambiaron
            prod.descripcion = row["desc"]
            prod.precioUnitario = precio
            prod.categoriaProducto = cat
            prod.tipoProducto = tipo
            prod.unidadMedida = uni
            prod.save()
            actualizados += 1
        else:
            creados += 1

    return creados, actualizados


if __name__ == '__main__':
    try:
        c, a = cargar_productos()
        print(f"Productos creados: {c}, actualizados: {a}")
    except Exception as e:
        print(f"Error al cargar productos: {e}")
