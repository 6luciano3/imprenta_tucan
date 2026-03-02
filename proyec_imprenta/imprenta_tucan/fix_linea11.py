filepath = r'automatizacion\services.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Reescribir linea 11 completa y correcta
lines[10] = (
    '        filas += (f\'<tr>\''
    ' + f\'<td style="padding:9px 12px;border-bottom:1px solid #e8edf2;">{cop.producto.nombreProducto}</td>\''
    ' + f\'<td style="padding:9px 12px;text-align:center;">{cant}</td>\''
    ' + \'<td style="padding:9px 12px;text-align:right;">\' + "{:,.0f}".format(precio).replace(",",".") + \'</td>\''
    ' + \'<td style="padding:9px 12px;text-align:right;font-weight:600;">\' + "{:,.0f}".format(sub).replace(",",".") + \'</td></tr>\')\n'
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Guardado OK')
print('Linea 11:', repr(lines[10][:150]))
