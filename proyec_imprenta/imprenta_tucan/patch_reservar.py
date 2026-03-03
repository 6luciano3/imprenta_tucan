filepath = r"pedidos/services.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

old = """def reservar_insumos_para_pedido(pedido):
    from insumos.models import Insumo
    from pedidos.models import OrdenProduccion
    consumos = calcular_consumo_pedido(pedido)
    for insumo_id, cantidad in consumos.items():
        insumo = Insumo.objects.select_for_update().get(idInsumo=insumo_id)
        if insumo.stock < cantidad:
            raise ValueError(f"Stock insuficiente para {insumo.nombre}")
        insumo.stock -= cantidad
        insumo.save()
    OrdenProduccion.objects.get_or_create(pedido=pedido)"""

new = """def reservar_insumos_para_pedido(pedido):
    from insumos.models import Insumo
    from pedidos.models import OrdenProduccion
    from auditoria.models import AuditEntry
    import json

    consumos = calcular_consumo_pedido(pedido)
    for insumo_id, cantidad in consumos.items():
        insumo = Insumo.objects.select_for_update().get(idInsumo=insumo_id)
        if insumo.stock < cantidad:
            raise ValueError(f"Stock insuficiente para {insumo.nombre}: "
                             f"disponible={insumo.stock}, requerido={cantidad}")
        stock_anterior = insumo.stock
        insumo.stock -= int(cantidad)
        insumo.save()

        # Registrar movimiento en auditoria
        AuditEntry.objects.create(
            app_label="insumos",
            model="Insumo",
            object_id=str(insumo.idInsumo),
            object_repr=str(insumo),
            action=AuditEntry.ACTION_UPDATE,
            changes=json.dumps({
                "stock": [stock_anterior, insumo.stock],
                "motivo": f"Pedido #{pedido.id} -> En Proceso",
                "cantidad_consumida": float(cantidad),
                "cliente": str(pedido.cliente),
            }, ensure_ascii=False),
            extra=json.dumps({
                "pedido_id": pedido.id,
                "insumo_codigo": insumo.codigo,
                "insumo_nombre": insumo.nombre,
            }, ensure_ascii=False),
        )

    OrdenProduccion.objects.get_or_create(pedido=pedido)"""

if old in content:
    content = content.replace(old, new)
    print("Reemplazo OK")
else:
    print("ERROR: funcion original no encontrada")
    # Mostrar fragmento para debug
    idx = content.find("def reservar_insumos_para_pedido")
    if idx >= 0:
        print("Funcion encontrada en pos:", idx)
        print(repr(content[idx:idx+300]))

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
