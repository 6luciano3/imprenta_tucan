import pathlib, re

# Patrones mas precisos y con menos falsos positivos
PATRONES = [
    # Credenciales reales hardcodeadas en Python
    (r'(?i)(password|passwd|secret_key|api_key|token|auth_key)\s*=\s*["\'][^"\']{6,}["\']', 'CREDENCIAL', ['.py']),
    # Emails reales (no placeholders ni templates Django)
    (r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', 'EMAIL', ['.py', '.html', '.js']),
    # IPs no locales
    (r'\b(?!127\.|0\.0\.|192\.168\.|10\.)(?:\d{1,3}\.){3}\d{1,3}\b', 'IP', ['.py', '.html']),
    # URLs externas hardcodeadas en Python (no en templates)
    (r'https?://(?!cdn\.|fonts\.|cdnjs\.|flaticon\.)[a-zA-Z0-9._-]+\.[a-zA-Z]{2,}/[^\s"\']{5,}', 'URL', ['.py']),
    # CUITs reales (formato XX-XXXXXXXX-X con digitos reales, no ceros)
    (r'\b\d{2}-(?!0{8})\d{7,8}-\d\b', 'CUIT', ['.py', '.html']),
    # Telefonos reales en Python (no CSS, no hex colors)
    (r'(?<![#\w])\+?(?:54|0)\s*\d{3,4}[\s.-]\d{6,8}(?!\w)', 'TELEFONO', ['.py']),
    # Numeros magicos de negocio en logica Python (scores, descuentos)
    (r'(?i)(?:score|descuento|porcentaje)\s*[><=!]+\s*(?!0\b)\d+(?:\.\d+)?(?!\s*#)', 'NUMERO_MAGICO', ['.py']),
    # Rutas absolutas hardcodeadas
    (r'[A-Za-z]:\\\\(?!Users\\\\Public)[^\s"\'\\\\]{10,}', 'RUTA_ABSOLUTA', ['.py']),
]

# Palabras que indican que es un dato de prueba/placeholder - ignorar
WHITELIST_LINEA = [
    'placeholder', 'ejemplo', 'example', 'test', 'demo', 'dummy', 'fake',
    'local', 'tucan.local', '{{ ', '{% ', 'no-reply', 'info@',
    '# ', 'TODO', 'FIXME', 'seed', 'populate', 'fixture',
]

IGNORAR_DIRS = {'migrations', '__pycache__', '.git', 'node_modules', 'staticfiles', 'media', 'sent_emails', 'venv', 'tests'}
IGNORAR_ARCHIVOS = {'settings.py', 'chequear_hardcoded.py', 'chequear_hardcoded_v2.py'}

resultados = {}
total = 0

for p in pathlib.Path('.').rglob('*'):
    if not p.is_file(): continue
    if any(ign in p.parts for ign in IGNORAR_DIRS): continue
    if p.name in IGNORAR_ARCHIVOS: continue

    try:
        txt = p.read_text(encoding='utf-8', errors='ignore')
        lineas = txt.splitlines()
        hallazgos = []

        for patron, tipo, extensiones in PATRONES:
            if p.suffix not in extensiones: continue
            for i, linea in enumerate(lineas, 1):
                linea_strip = linea.strip()
                # Saltar comentarios
                if linea_strip.startswith(('#', '//', '/*', '*', '<!--')): continue
                # Saltar whitelist
                if any(w in linea.lower() for w in WHITELIST_LINEA): continue
                matches = re.findall(patron, linea)
                if matches:
                    match_val = matches[0] if isinstance(matches[0], str) else str(matches[0])
                    hallazgos.append((i, tipo, match_val, linea_strip[:100]))

        if hallazgos:
            resultados[str(p)] = hallazgos
            total += len(hallazgos)
    except: pass

# Reporte agrupado por tipo
print(f'{"="*70}')
print(f'REPORTE DATOS HARDCODEADOS v2 - {total} hallazgos reales en {len(resultados)} archivos')
print(f'{"="*70}\n')

PRIORIDAD = {'CREDENCIAL': 1, 'CUIT': 2, 'EMAIL': 3, 'NUMERO_MAGICO': 4, 'URL': 5, 'IP': 6, 'TELEFONO': 7, 'RUTA_ABSOLUTA': 8}

for archivo, hallazgos in sorted(resultados.items()):
    hallazgos_ordenados = sorted(hallazgos, key=lambda x: PRIORIDAD.get(x[1], 9))
    print(f'>>> {archivo}')
    for linea_num, tipo, valor, contenido in hallazgos_ordenados:
        emoji = {'CREDENCIAL': 'CRITICO', 'CUIT': 'DATO', 'EMAIL': 'DATO', 'NUMERO_MAGICO': 'LOGICA', 'URL': 'URL', 'IP': 'IP', 'TELEFONO': 'DATO', 'RUTA_ABSOLUTA': 'RUTA'}.get(tipo, '')
        print(f'  L{linea_num:4d} [{emoji}] {tipo}: {valor}')
    print()

if not resultados:
    print('No se encontraron datos hardcodeados relevantes.')

print(f'{"="*70}')
print('Falsos positivos excluidos: colores CSS, placeholders, seeds/fixtures, templates Django')
print(f'{"="*70}')
