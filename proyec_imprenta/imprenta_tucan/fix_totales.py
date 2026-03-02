filepath = r'automatizacion\services.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Reemplazar formato ,.0f por propio con punto
content = content.replace('{precio:,.0f}', "'{:,.0f}'.format(precio).replace(',','.')")
content = content.replace('{sub:,.0f}', "'{:,.0f}'.format(sub).replace(',','.')")
content = content.replace('{subtotal:,.0f}', "'{:,.0f}'.format(subtotal).replace(',','.')")
content = content.replace('{desc_valor:,.0f}', "'{:,.0f}'.format(desc_valor).replace(',','.')")
content = content.replace('{total:,.0f}', "'{:,.0f}'.format(total).replace(',','.')")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print('Guardado OK')
