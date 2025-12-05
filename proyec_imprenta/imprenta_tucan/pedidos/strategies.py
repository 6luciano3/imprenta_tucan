from abc import ABC, abstractmethod


class EstrategiaCalculoConsumo(ABC):
    @abstractmethod
    def consumo_por_insumo(self, pedido):
        pass


class CalculoFolleto(EstrategiaCalculoConsumo):
    def consumo_por_insumo(self, pedido):
        receta = pedido.producto.receta
        resultado = []
        for r in receta:
            insumo_id = r['insumo_id']
            cantidad_por_unidad = r['cantidad_por_unidad']
            total = cantidad_por_unidad * pedido.tiraje
            resultado.append((insumo_id, total))
        return resultado


class CalculoTarjeta(EstrategiaCalculoConsumo):
    def consumo_por_insumo(self, pedido):
        return CalculoFolleto().consumo_por_insumo(pedido)


ESTRATEGIAS = {
    'folleto': CalculoFolleto,
    'tarjeta': CalculoTarjeta,
}


def seleccionar_estrategia(producto):
    cls = ESTRATEGIAS.get(producto.tipo, CalculoFolleto)
    return cls()
