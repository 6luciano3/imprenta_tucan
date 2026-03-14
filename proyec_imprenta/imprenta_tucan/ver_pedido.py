import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()

from pedidos.models import Pedido

try:
    p = Pedido.objects.get(pk=326)
    print('Pedido encontrado:')
    print('  ID:       ' + str(p.id))
    print('  Cliente:  ' + str(p.cliente))
    print('  Estado:   ' + str(p.estado))
    print('  Monto:    ' + str(p.monto_total))
    print('  Entrega:  ' + str(p.fecha_entrega))
    print('  Producto: ' + str(getattr(p, 'producto', 'Sin campo producto')))
except Pedido.DoesNotExist:
    print('ERROR: Pedido 326 no existe en la base de datos')
except Exception as e:
    print('ERROR: ' + str(e))
