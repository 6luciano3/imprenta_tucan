filepath = r'automatizacion\services.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Corregir linea 11 (indice 10)
line = lines[10]
print('ANTES:', repr(line[100:200]))

# Reemplazar las celdas vacias/rotas con los valores reales
import re
line = re.sub(
    r'f\'<td style="padding:9px 12px;text-align:right;">[^{]*</td>\'',
    'f\'<td style="padding:9px 12px;text-align:right;">{precio:,.0f}</td>\'',
    line,
    count=1
)
line = re.sub(
    r'f\'<td style="padding:9px 12px;text-align:right;font-weight:600;">[^{]*</td></tr>\'',
    'f\'<td style="padding:9px 12px;text-align:right;font-weight:600;">{sub:,.0f}</td></tr>\'',
    line,
    count=1
)
lines[10] = line
print('DESPUES:', repr(line[100:200]))

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Guardado OK')
