class PedidoRepository:
    def __init__(self, model):
        self.model = model

    def obtener_pendientes(self):
        return self.model.objects.filter(estado='Pendiente')

    def obtener_por_cliente(self, cliente_id):
        return self.model.objects.filter(cliente_id=cliente_id)

    def guardar(self, pedido):
        pedido.save()
        return pedido
