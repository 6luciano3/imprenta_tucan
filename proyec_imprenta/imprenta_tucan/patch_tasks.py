import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()

path = 'automatizacion/tasks.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

MARCA = "        # Notificar al staff\n        try:\n            from usuarios.models import Usuario, Notificacion\n            mensaje = f'{total} oferta(s) vencieron sin respuesta del cliente y fueron cerradas autom\u00e1ticamente.'\n            for u in Usuario.objects.filter(is_staff=True):\n                Notificacion.objects.create(usuario=u, mensaje=mensaje)\n        except Exception:\n            pass\n\n        return f'vencer_ofertas: {total} oferta(s) marcadas como vencidas'"

NUEVO = """        # Notificar al cliente por email
        try:
            from core.notifications.engine import enviar_notificacion
            from automatizacion.models import OfertaPropuesta as OP
            for oferta in OP.objects.filter(id__in=vencidas_ids).select_related('cliente'):
                cliente = oferta.cliente
                if not getattr(cliente, 'email_verificado', False):
                    continue
                enviar_notificacion(
                    destinatario=cliente.email,
                    canal='email',
                    asunto=f'Tu oferta "{oferta.titulo}" ha vencido',
                    mensaje=(
                        f'Hola {cliente.nombre}, '
                        f'la oferta "{oferta.titulo}" que preparamos especialmente para vos '
                        f'ha vencido sin ser respondida. '
                        f'Comunicate con nosotros si queres que generemos una nueva propuesta.'
                    ),
                )
        except Exception:
            pass
        # Notificar al staff
        try:
            from usuarios.models import Usuario, Notificacion
            mensaje = f'{total} oferta(s) vencieron sin respuesta del cliente y fueron cerradas autom\u00e1ticamente.'
            for u in Usuario.objects.filter(is_staff=True):
                Notificacion.objects.create(usuario=u, mensaje=mensaje)
        except Exception:
            pass

        return f'vencer_ofertas: {total} oferta(s) marcadas como vencidas'"""

if MARCA in content:
    content = content.replace(MARCA, NUEVO)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK - tasks.py actualizado')
else:
    print('ERROR - bloque no encontrado, buscando coincidencia parcial...')
    if 'Notificar al staff' in content and 'vencer_ofertas' in content:
        print('El archivo tiene el contenido pero el formato difiere')
    else:
        print('Contenido no encontrado en el archivo')
