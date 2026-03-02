filepath = r'automatizacion\services.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

def fmt(n):
    return "{:,.0f}".format(n).replace(",",".")

# Linea 11 - filas de productos
lines[10] = (
    '        filas += (f\'<tr>\''
    ' + f\'<td style="padding:9px 12px;border-bottom:1px solid #e8edf2;">{cop.producto.nombreProducto}</td>\''
    ' + f\'<td style="padding:9px 12px;text-align:center;">{cant}</td>\''
    ' + \'<td style="padding:9px 12px;text-align:right;">$\' + "{:,.0f}".format(precio).replace(",",".") + \'</td>\''
    ' + \'<td style="padding:9px 12px;text-align:right;font-weight:600;">$\' + "{:,.0f}".format(sub).replace(",",".") + \'</td></tr>\')\n'
)

# Buscar y corregir lineas 43, 44, 45 (subtotal, descuento, total)
for i, line in enumerate(lines):
    if "Subtotal</span><span>" in line and "subtotal" in line:
        lines[i] = line.replace(
            line[line.find("<span>$"):line.find("</span></div>'")+len("</span></div>'")],
            ""
        )
        # Reescribir completa
        indent = "                   "
        lines[i] = (indent + 
            'f\'<div style="display:flex;justify-content:space-between;color:#546e7a;margin-bottom:4px;">\''+
            ' + \'<span>Subtotal</span><span>$\' + "{:,.0f}".format(subtotal).replace(",",".") + \'</span></div>\',\n')
        print(f"Linea {i+1} subtotal reescrita")
    elif "Descuento" in line and "desc_valor" in line:
        indent = "                   "
        lines[i] = (indent +
            'f\'<div style="display:flex;justify-content:space-between;color:#c62828;font-weight:600;margin-bottom:4px;">\''+
            ' + f\'<span>Descuento ({descuento:.0f}%)</span><span>-$\' + "{:,.0f}".format(desc_valor).replace(",",".") + \'</span></div>\',\n')
        print(f"Linea {i+1} descuento reescrita")
    elif "Total Final</span><span>" in line and "total" in line:
        indent = "                   "
        lines[i] = (indent +
            'f\'<div style="display:flex;justify-content:space-between;color:#2e7d32;font-weight:700;font-size:14px;padding-top:6px;border-top:1px solid #e3eaf2;">\''+
            ' + \'<span>Total Final</span><span>$\' + "{:,.0f}".format(total).replace(",",".") + \'</span></div>\'\n')
        print(f"Linea {i+1} total reescrita")

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Guardado OK')
