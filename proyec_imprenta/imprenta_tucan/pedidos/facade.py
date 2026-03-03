from .repository import PedidoRepository
from .unit_of_work import UnitOfWork
from insumos.models import Insumo


class PresupuestoFacade:
    def __init__(self, pedido):
        self.pedido = pedido

    def generar_presupuesto(self):
        from .services import calcular_consumo_pedido
        consumos = calcular_consumo_pedido(self.pedido)

        detalles = []
        total = 0
        for insumo_id, cantidad in consumos.items():
            insumo = Insumo.objects.get(idInsumo=insumo_id)
            precio_unitario = self._obtener_precio_insumo(insumo)
            monto = precio_unitario * cantidad
            detalles.append({
                'insumo': insumo.nombre,
                'cantidad': cantidad,
                'precio_unitario': float(precio_unitario),
                'monto': float(monto),
            })
            total += monto

        presupuesto = {
            'pedido_id': self.pedido.id,
            'detalles': detalles,
            'total': float(total),
        }
        return presupuesto

    def _obtener_precio_insumo(self, insumo):
        return 1.0

    def confirmar_y_reservar_insumos(self):
        from .services import reservar_insumos_para_pedido
        with UnitOfWork():
            reservar_insumos_para_pedido(self.pedido)
            self.pedido.estado = 'Reservado'
            self.pedido.save()
