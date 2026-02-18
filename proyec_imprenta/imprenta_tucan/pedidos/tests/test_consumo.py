import pytest
from productos.models import Producto
from pedidos.models import Pedido, EstadoPedido
from clientes.models import Cliente
from pedidos.strategies import seleccionar_estrategia
from insumos.models import Insumo
from configuracion.models import Formula


@pytest.mark.django_db
def test_calculo_folleto():
    cliente = Cliente.objects.create(nombre="Test", apellido="Test", email="test@test.com", telefono="123456")
    insumo = Insumo.objects.create(nombre="Papel", codigo="PAP001")
    formula = Formula.objects.create(insumo=insumo, codigo="F001", nombre="Formula Folleto", expresion="x*2", variables_json=[{"nombre": "x", "valor": 1}])
    estado = EstadoPedido.objects.create(nombre="Pendiente")
    producto = Producto.objects.create(
        nombreProducto="Folleto",
        precioUnitario=10,
        formula=formula
    )
    # Crear la receta para el producto
    from productos.models import ProductoInsumo
    ProductoInsumo.objects.create(producto=producto, insumo=insumo, cantidad_por_unidad=2)
    pedido = Pedido.objects.create(cliente=cliente, producto=producto, cantidad=100, fecha_entrega="2026-12-31", monto_total=100, estado=estado)
    estrategia = seleccionar_estrategia(producto)
    consumos = estrategia.consumo_por_insumo(pedido)
    assert consumos == [(insumo.idInsumo, 200)]
