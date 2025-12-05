from django.core.management.base import BaseCommand
from pedidos.models import Pedido
from productos.models import Producto
from formulas.models import FormulaProducto, InsumoFormula, Insumo


class Command(BaseCommand):
    help = 'Chequea que todos los pedidos tengan insumo de tipo papel en la receta.'

    def handle(self, *args, **options):
        pedidos = Pedido.objects.all()
        pedidos_sin_papel = []
        for pedido in pedidos:
            producto = pedido.producto
            receta = FormulaProducto.objects.filter(producto=producto).first()
            if not receta:
                pedidos_sin_papel.append(pedido.id)
                continue
            insumos = InsumoFormula.objects.filter(formula=receta)
            tiene_papel = False
            for insumo_formula in insumos:
                insumo = getattr(insumo_formula, 'insumo', None)
                if insumo and getattr(insumo, 'tipo', '').lower() == 'papel':
                    tiene_papel = True
                    break
            if not tiene_papel:
                pedidos_sin_papel.append(pedido.id)
        if not pedidos_sin_papel:
            self.stdout.write(self.style.SUCCESS('Todos los pedidos tienen insumo de tipo papel en la receta.'))
        else:
            self.stdout.write(self.style.WARNING(f'Pedidos sin insumo de tipo papel: {pedidos_sin_papel}'))
