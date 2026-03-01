import pathlib, re

PATRONES = [
    # URLs hardcodeadas (no variables de entorno ni templates Django)
    (r'https?://(?!cdn\.|fonts\.|cdnjs\.)[a-zA-Z0-9._-]+\.[a-zA-Z]{2,}(?:/[^\s"\']*)?', 'URL hardcodeada'),
    # IPs
    (r'\b(?:\d{1,3}\.){3}\d{1,3}\b', 'IP hardcodeada'),
    # Passwords / secrets en codigo
    (r'(?i)(password|passwd|secret|token|api_key|apikey|auth_key)\s*=\s*["\'][^"\']{3,}["\']', 'Credencial hardcodeada'),
    # Emails hardcodeados (excepto los de ejemplo/test)
    (r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', 'Email hardcodeado'),
    # Numeros de telefono
    (r'(?<!\w)(\+?54\s?)?(\(?\d{3,4}\)?[\s.-]?)?\d{6,8}(?!\w)', 'Telefono hardcodeado'),
    # CUIT / DNI (11 digitos seguidos)
    (r'\b\d{11}\b', 'CUIT/DNI hardcodeado'),
    # Rutas absolutas Windows/Linux en codigo (no en settings)
    (r'[A-Z]:\\\\[^\s"\']+|/home/[^\s"\']+|/var/[^\s"\']+', 'Ruta absoluta hardcodeada'),
    # Claves AWS
    (r'(?i)(aws_access_key|aws_secret)[^=]*=\s*["\'][A-Za-z0-9/+=]{10,}["\']', 'Clave AWS hardcodeada'),
    # Numeros magicos en logica de negocio (descuentos, scores fijos)
    (r'(?<![.\w])(?:score|descuento|porcentaje|limite)\s*[=><!]+\s*\d+(?!\s*,)', 'Numero magico en logica'),
]

EXTENSIONES = {'.py', '.html', '.js', '.env', '.cfg', '.ini', '.json', '.yml', '.yaml'}
IGNORAR_DIRS = {'migrations', '__pycache__', '.git', 'node_modules', 'staticfiles', 'media', 'sent_emails', 'venv', '.env'}
IGNORAR_ARCHIVOS = {'settings.py', 'chequear_hardcoded.py'}

# Whitelist - falsos positivos conocidos
WHITELIST = [
    'example.com', 'localhost', '127.0.0.1', '0.0.0.0',
    'fonts.googleapis', 'cdn.tailwindcss', 'cdnjs.cloudflare',
    'flaticon.com', 'no-reply@', 'info@imprenta',
    'test', 'ejemplo', 'example', 'dummy',
    '00000000000',  # CUIT default
]

resultados = {}
total = 0

for p in pathlib.Path('.').rglob('*'):
    if not p.is_file():
        continue
    if p.suffix not in EXTENSIONES:
        continue
    if any(ign in p.parts for ign in IGNORAR_DIRS):
        continue
    if p.name in IGNORAR_ARCHIVOS:
        continue

    try:
        txt = p.read_text(encoding='utf-8', errors='ignore')
        lineas = txt.splitlines()
        hallazgos = []

        for patron, descripcion in PATRONES:
            for i, linea in enumerate(lineas, 1):
                # Saltar comentarios y lineas de whitelist
                linea_lower = linea.lower()
                if any(w in linea_lower for w in WHITELIST):
                    continue
                # Saltar lineas que son solo imports o print de debug
                if linea.strip().startswith(('#', '//', '/*', '*')):
                    continue
                matches = re.findall(patron, linea)
                if matches:
                    match_str = str(matches[0]) if isinstance(matches[0], str) else str(matches[0])
                    if len(match_str) > 3:
                        hallazgos.append((i, descripcion, linea.strip()[:120]))

        if hallazgos:
            resultados[str(p)] = hallazgos
            total += len(hallazgos)

    except Exception as e:
        pass

# Reporte
print(f'{"="*70}')
print(f'REPORTE DE DATOS HARDCODEADOS - {total} hallazgos en {len(resultados)} archivos')
print(f'{"="*70}\n')

for archivo, hallazgos in sorted(resultados.items()):
    print(f'>>> {archivo}  ({len(hallazgos)} hallazgos)')
    for linea_num, tipo, contenido in hallazgos:
        print(f'  L{linea_num:4d} [{tipo}]')
        print(f'         {contenido}')
    print()

if not resultados:
    print('No se encontraron datos hardcodeados.')

print(f'{"="*70}')
print('NOTA: Revisar manualmente los hallazgos - pueden existir falsos positivos.')
print(f'{"="*70}')
