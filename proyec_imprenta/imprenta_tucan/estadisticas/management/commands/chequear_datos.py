from django.core.management.base import BaseCommand
from clientes.models import Cliente
from productos.models import Producto
from pedidos.models import Pedido


class Command(BaseCommand):
    help = 'Chequea si existen datos reales en las tablas Cliente, Producto y Pedido para estadísticas.'

    def handle(self, *args, **options):
        clientes = Cliente.objects.count()
        productos = Producto.objects.count()
        pedidos = Pedido.objects.count()
        self.stdout.write(f"Clientes: {clientes}")
        self.stdout.write(f"Productos: {productos}")
        self.stdout.write(f"Pedidos: {pedidos}")
        if clientes == 0:
            self.stdout.write(self.style.WARNING("No hay clientes cargados. Debes importar datos reales."))
        if productos == 0:
            self.stdout.write(self.style.WARNING("No hay productos cargados. Debes importar datos reales."))
        if pedidos == 0:
            self.stdout.write(self.style.WARNING("No hay pedidos cargados. Debes importar datos reales."))
        if clientes and productos and pedidos:
            self.stdout.write(self.style.SUCCESS("¡La base de datos tiene datos reales para estadísticas!"))
