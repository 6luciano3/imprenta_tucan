import pathlib, re

p = pathlib.Path('imprenta_tucan/settings.py')
if not p.exists():
    # Buscar settings en cualquier subcarpeta
    for sp in pathlib.Path('.').rglob('settings.py'):
        if 'imprenta' in str(sp).lower() or 'config' in str(sp).lower():
            p = sp
            break

txt = p.read_text(encoding='utf-8')
old = "'configuracion.context_processors.module_visibility'"
new = "'configuracion.context_processors.module_visibility',\n                    'configuracion.context_processors.empresa_context'"

if old in txt and 'empresa_context' not in txt:
    txt = txt.replace(old, new)
    p.write_text(txt, encoding='utf-8')
    print(f'settings.py actualizado: {p}')
else:
    print('Ya registrado o patron no encontrado')
    # Mostrar context_processors actual
    for i, l in enumerate(txt.splitlines(), 1):
        if 'context_processors' in l or 'module_visibility' in l:
            print(f'  L{i}: {l}')
