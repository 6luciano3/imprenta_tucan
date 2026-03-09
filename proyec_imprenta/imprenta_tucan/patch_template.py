import pathlib

path = pathlib.Path('automatizacion/templates/automatizacion/ofertas_propuestas.html')
src = path.read_text(encoding='utf-8')

old = '''                            <a href="{% url 'aprobar_oferta' o.id %}"
                               class="text-blue-600 hover:text-blue-800 flex items-center gap-1"
                               title="Enviar">
                                <span class="material-symbols-outlined text-sm">outgoing_mail</span>
                            </a>'''

if old in src:
    src = src.replace(old, '')
    path.write_text(src, encoding='utf-8')
    print('OK boton eliminado')
else:
    print('NO ENCONTRADO - buscando variante')
    idx = src.find('aprobar_oferta')
    print('Contexto:', repr(src[max(0,idx-50):idx+150]) if idx != -1 else 'No existe')
