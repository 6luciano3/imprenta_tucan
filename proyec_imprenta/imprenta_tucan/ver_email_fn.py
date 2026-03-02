import pathlib

# Buscar enviar_oferta_email en todo el proyecto
print('=== enviar_oferta_email ===')
for p in pathlib.Path('.').rglob('*.py'):
    if '__pycache__' in str(p): continue
    txt = p.read_text(encoding='utf-8', errors='ignore')
    if 'enviar_oferta_email' in txt:
        for i, l in enumerate(txt.splitlines(), 1):
            if 'enviar_oferta_email' in l or ('def enviar' in l and 'oferta' in l):
                print(f'  {p} L{i}: {l.strip()}')

# Ver template oferta_individual.html
print('\n=== oferta_individual.html ===')
for p in pathlib.Path('.').rglob('oferta_individual.html'):
    print(f'Archivo: {p}')
    print(p.read_text(encoding='utf-8'))
