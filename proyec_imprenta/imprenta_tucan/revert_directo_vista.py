with open("automatizacion/views.py", "r", encoding="utf-8") as f:
    content = f.read()

old1 = """    # Solo insumos directos de produccion
    insumos_directos = list(Insumo.objects.filter(tipo='directo', activo=True))

    # Get all proposals para insumos directos
    propuestas_qs = CompraPropuesta.objects.select_related('insumo', 'proveedor_recomendado', 'borrador_oc', 'consulta_stock') \\
        .filter(insumo__tipo='directo')

    # Build a dict: insumo_id -> propuesta
    propuestas_dict = {p.insumo.pk: p for p in propuestas_qs}

    # Compose all insumos to show: union de insumos directos y propuestas existentes
    all_insumos = {i.pk: i for i in insumos_directos}"""

new1 = """    # Get all proposals
    propuestas_qs = CompraPropuesta.objects.select_related('insumo', 'proveedor_recomendado', 'borrador_oc', 'consulta_stock')

    # Build a dict: insumo_id -> propuesta
    propuestas_dict = {p.insumo.pk: p for p in propuestas_qs}

    # Compose all insumos to show
    all_insumos = {}"""

old2 = """    propuestas_qs = CompraPropuesta.objects.select_related('insumo', 'proveedor_recomendado', 'borrador_oc', 'consulta_stock') \\
        .filter(insumo__tipo='directo')"""

new2 = """    propuestas_qs = CompraPropuesta.objects.select_related('insumo', 'proveedor_recomendado', 'borrador_oc', 'consulta_stock')"""

changes = 0
if old1 in content:
    content = content.replace(old1, new1)
    changes += 1
    print("OK: primer bloque revertido")
else:
    print("ERROR: primer bloque no encontrado")

if old2 in content:
    content = content.replace(old2, new2)
    changes += 1
    print("OK: segundo bloque revertido")
else:
    print("ERROR: segundo bloque no encontrado")

with open("automatizacion/views.py", "w", encoding="utf-8") as f:
    f.write(content)
print(f"{changes} cambios aplicados")
