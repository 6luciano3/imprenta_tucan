import pathlib
template_path = pathlib.Path('auditoria/templates/auditoria/lista_auditoria.html')
contenido = open('auditoria_nuevo.html', encoding='utf-8').read()
template_path.write_text(contenido, encoding='utf-8')
print('OK lista_auditoria.html actualizado')
