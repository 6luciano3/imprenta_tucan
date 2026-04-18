"""
Tests de integración del flujo de stock en pedidos.
Reemplaza la versión pytest anterior que usaba campos eliminados del modelo Pedido.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from clientes.models import Cliente
from configuracion.models import Formula
from insumos.models import Insumo
from pedidos.models import EstadoPedido, LineaPedido, Pedido
from productos.models import Producto, ProductoInsumo


class StockPedidoTests(TestCase):
    def setUp(self):
        self.insumo = Insumo.objects.create(
            nombre="Tinta Negra", codigo="INK-001",
            stock=100, precio_unitario=10, activo=True,
        )
        formula = Formula.objects.create(
            insumo=self.insumo, codigo="F001", nombre="Formula Test",
            expresion="tirada * 1", variables_json=[], version=1, activo=True,
        )
        self.producto = Producto.objects.create(
            nombreProducto="Tarjeta", precioUnitario=50,
            activo=True, formula=formula,
        )
        ProductoInsumo.objects.create(
            producto=self.producto, insumo=self.insumo, cantidad_por_unidad=2
        )
        self.cliente = Cliente.objects.create(
            nombre="Test", apellido="Stock",
            email="test@stock.com", telefono="123456",
            cuit="20-33333333-3",
        )
        self.estado_pendiente, _ = EstadoPedido.objects.get_or_create(nombre="pendiente")
        self.estado_proceso, _ = EstadoPedido.objects.get_or_create(nombre="proceso")

    def _crear_pedido(self, cantidad):
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            fecha_entrega=date.today() + timedelta(days=7),
            monto_total=Decimal("500.00"),
            estado=self.estado_pendiente,
        )
        LineaPedido.objects.create(
            pedido=pedido,
            producto=self.producto,
            cantidad=cantidad,
            precio_unitario=Decimal("50.00"),
        )
        return pedido

    def test_crear_pedido_y_cambiar_estado_descuenta_stock(self):
        pedido = self._crear_pedido(10)
        stock_antes = self.insumo.stock

        pedido.estado = self.estado_proceso
        pedido.save()

        self.insumo.refresh_from_db()
        # cantidad_por_unidad=2, cantidad=10 → 20 descontados
        self.assertEqual(self.insumo.stock, stock_antes - 20)

    def test_stock_no_se_descuenta_al_crear_en_pendiente(self):
        stock_antes = self.insumo.stock
        self._crear_pedido(10)
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock, stock_antes)

    def test_stock_con_insumo_costo_fijo(self):
        """Insumo con es_costo_fijo=True: cantidad fija por trabajo, no multiplica."""
        ProductoInsumo.objects.filter(producto=self.producto).update(es_costo_fijo=True)
        pedido = self._crear_pedido(cantidad=100)
        stock_antes = self.insumo.stock

        pedido.estado = self.estado_proceso
        pedido.save()

        self.insumo.refresh_from_db()
        # costo_fijo: cantidad_por_unidad=2 independiente de cantidad=100
        self.assertEqual(self.insumo.stock, stock_antes - 2)
