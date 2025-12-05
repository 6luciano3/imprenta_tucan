import pytest
from pedidos.models import Producto, Pedido, Cliente
from pedidos.strategies import seleccionar_estrategia


@pytest.mark.django_db
def test_calculo_folleto():
    cliente = Cliente.objects.create(nombre="Test", email="test@test.com")
    producto = Producto.objects.create(
        nombre="Folleto",
        tipo="folleto",
        receta=[{"insumo_id": 1, "cantidad_por_unidad": 2}]
    )
    pedido = Pedido.objects.create(cliente=cliente, producto=producto, tiraje=100)
    estrategia = seleccionar_estrategia(producto)
    consumos = estrategia.consumo_por_insumo(pedido)
    assert consumos == [(1, 200)]
