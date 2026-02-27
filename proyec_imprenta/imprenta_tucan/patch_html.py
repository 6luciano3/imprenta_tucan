import pathlib
p = pathlib.Path('automatizacion/templates/automatizacion/ofertas_propuestas.html')
txt = p.read_text(encoding='utf-8')

# Fix 1: boton ver-combos agrega cliente.id
antes = len([l for l in txt.splitlines() if 'openCombosModal()' in l])
txt = txt.replace('onclick="openCombosModal()"', "onclick=\"openCombosModal('{{ oferta.cliente.id }}')\"")
despues = len([l for l in txt.splitlines() if 'openCombosModal()' in l])
print(f'Botones parcheados: {antes - despues} reemplazos')

# Fix 2: funcion JS
old_fn = "function openCombosModal() {"
new_fn = """function openCombosModal(clienteId) {
        const combosModal = document.getElementById('combosModal');
        const combosContent = document.getElementById('combosModalContent');
        if (!clienteId) {
            combosContent.innerHTML = '<div class=\"text-center text-red-500 py-10\">No se pudo identificar el cliente.</div>';
            combosModal.classList.remove('hidden'); combosModal.classList.add('flex'); return;
        }
        combosModal.classList.remove('hidden');
        combosModal.classList.add('flex');
        combosContent.innerHTML = '<div class=\"flex items-center justify-center py-10 text-gray-400\"><span class=\"text-sm\">Generando combo...</span></div>';
        fetch('/automatizacion/combos-oferta/?popup=1&cliente_id=' + clienteId)
            .then(resp => { if (!resp.ok) throw new Error('HTTP ' + resp.status); return resp.text(); })
            .then(html => { combosContent.innerHTML = html; })
            .catch(err => { combosContent.innerHTML = '<div class=\"text-center text-red-500 py-10\">Error: ' + err.message + '</div>'; });"""

if old_fn in txt:
    txt = txt.replace(old_fn, new_fn, 1)
    print('Funcion JS parcheada OK')
else:
    print('ADVERTENCIA: funcion openCombosModal no encontrada exactamente')

p.write_text(txt, encoding='utf-8')
print('ofertas_propuestas.html guardado OK')
