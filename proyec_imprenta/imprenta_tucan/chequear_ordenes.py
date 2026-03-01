import pathlib

terminos = ['OrdenProduccion', 'OrdenCompra']

resultados = {}
for p in pathlib.Path('.').rglob('*.py'):
    if any(skip in str(p) for skip in ['migrations', '__pycache__', '.env']):
        continue
    try:
        txt = p.read_text(encoding='utf-8', errors='ignore')
        for termino in terminos:
            if termino in txt:
                for i, l in enumerate(txt.splitlines(), 1):
                    if termino in l:
                        key = str(p)
                        if key not in resultados:
                            resultados[key] = []
                        resultados[key].append(f'  L{i:4d} [{termino}]: {l.strip()}')
    except:
        pass

if resultados:
    print(f'Se encontraron referencias en {len(resultados)} archivo(s):\n')
    for archivo, lineas in sorted(resultados.items()):
        print(f'>>> {archivo}')
        for l in lineas:
            print(l)
        print()
else:
    print('No se encontraron referencias a OrdenProduccion ni OrdenCompra.')
