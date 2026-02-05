from django.core.management.base import BaseCommand
from pedidos.models import Pedido
from productos.models import ProductoInsumo


class Command(BaseCommand):
    help = 'Chequea que todos los pedidos tengan receta definida (ProductoInsumo) y al menos un insumo requerido cargado.'

    def handle(self, *args, **options):
        pedidos = Pedido.objects.all()
        sin_receta = []
        sin_insumos = []
        for pedido in pedidos:
            producto = pedido.producto
            # La receta se define por entradas ProductoInsumo para el producto
            insumos_receta = ProductoInsumo.objects.filter(producto=producto)
            if not insumos_receta.exists():
                # Sin receta definida (no hay vínculo producto-insumo)
                sin_receta.append(pedido.id)
                continue
            # Si existe receta pero no hay insumos (por seguridad, aunque el exists anterior lo cubre)
            if insumos_receta.count() == 0:
                sin_insumos.append(pedido.id)
        if not sin_receta and not sin_insumos:
            self.stdout.write(self.style.SUCCESS('Todos los pedidos tienen receta e insumos requeridos definidos.'))
        else:
            if sin_receta:
                self.stdout.write(self.style.WARNING(f'Pedidos sin receta definida (ProductoInsumo): {sin_receta}'))
            if sin_insumos:
                self.stdout.write(self.style.WARNING(f'Pedidos sin insumos requeridos en receta: {sin_insumos}'))
