filepath = r"pedidos/models.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

old1 = "            estado_proceso = self.estado if self.estado.nombre.lower() == 'proceso' else None"
new1 = "            estado_proceso = self.estado if 'proceso' in self.estado.nombre.lower() else None"

old2 = "            if old_estado != 'proceso' and new_estado == 'proceso':"
new2 = "            if 'proceso' not in old_estado and 'proceso' in new_estado:"

old3 = "            estado_proceso = EstadoPedido.objects.filter(nombre__iexact='proceso').first()"
new3 = "            estado_proceso = EstadoPedido.objects.filter(nombre__icontains='proceso').first()"

changes = 0
for old, new in [(old1, new1), (old2, new2), (old3, new3)]:
    if old in content:
        content = content.replace(old, new)
        changes += 1
        print(f"OK: {old[:60]}...")
    else:
        print(f"NO ENCONTRADO: {old[:60]}...")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print(f"\n{changes} cambios aplicados")
