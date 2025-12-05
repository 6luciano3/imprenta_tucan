import pytest
from insumos.models import Insumo
from productos.models import Producto
from pedidos.models import Pedido, EstadoPedido


@pytest.mark.django_db
def test_crear_pedido_y_cambiar_estado_descuenta_stock():
    # Crear insumo
    insumo = Insumo.objects.create(
        nombre="Tinta Negra",
        codigo="INK-001",
        cantidad=100,
        stock=100,
        precio_unitario=10,
        precio=10,
        activo=True
    )
    # Crear producto con receta
    producto = Producto.objects.create(
        nombreProducto="Tarjeta",
        precioUnitario=50,
        activo=True
    )
    # Relacionar receta
    from productos.models import ProductoInsumo
    ProductoInsumo.objects.create(
        producto=producto,
        insumo=insumo,
        cantidad_por_unidad=2
    )
    # Crear estados
    estado_pendiente = EstadoPedido.objects.create(nombre="pendiente")
    estado_proceso = EstadoPedido.objects.create(nombre="proceso")
    # Crear pedido
    pedido = Pedido.objects.create(
        cliente_id=1,  # Asume cliente con id=1 existe
        producto=producto,
        cantidad=10,
        monto_total=500,
        estado=estado_pendiente,
        fecha_entrega="2025-12-01"
    )
    stock_antes = insumo.stock
    # Cambiar estado a 'proceso'
    pedido.estado = estado_proceso
    pedido.save()
    insumo.refresh_from_db()
    # Verificar que el stock se descontó correctamente
    assert insumo.stock == stock_antes - (2 * 10)
