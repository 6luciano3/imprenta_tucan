from django.core.management.base import BaseCommand
from pedidos.models import Pedido
from productos.models import Producto
from formulas.models import FormulaProducto, InsumoFormula


class Command(BaseCommand):
    help = 'Chequea que todos los pedidos tengan receta definida y los insumos requeridos cargados.'

    def handle(self, *args, **options):
        pedidos = Pedido.objects.all()
        sin_receta = []
        sin_insumos = []
        for pedido in pedidos:
            producto = pedido.producto
            receta = FormulaProducto.objects.filter(producto=producto).first()
            if not receta:
                sin_receta.append(pedido.id)
                continue
            insumos = InsumoFormula.objects.filter(formula=receta)
            if not insumos.exists():
                sin_insumos.append(pedido.id)
        if not sin_receta and not sin_insumos:
            self.stdout.write(self.style.SUCCESS('Todos los pedidos tienen receta e insumos requeridos definidos.'))
        else:
            if sin_receta:
                self.stdout.write(self.style.WARNING(f'Pedidos sin receta definida: {sin_receta}'))
            if sin_insumos:
                self.stdout.write(self.style.WARNING(f'Pedidos sin insumos requeridos: {sin_insumos}'))
