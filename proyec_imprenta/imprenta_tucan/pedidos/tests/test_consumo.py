"""
Tests del sistema de consumo de insumos (pedidos/services.py + pedidos/utils.py).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from clientes.models import Cliente
from configuracion.models import Formula
from insumos.models import Insumo
from pedidos.models import EstadoPedido, LineaPedido, Pedido
from pedidos.services import calcular_consumo_pedido, calcular_consumo_producto
from pedidos.utils import verificar_insumos_para_lineas, ajustar_insumos_por_diferencia
from productos.models import Producto, ProductoInsumo


_formula_counter = 0


def _make_insumo(nombre, codigo, stock=100, tipo='directo'):
    return Insumo.objects.create(
        nombre=nombre, codigo=codigo,
        stock=stock, precio_unitario=1, activo=True, tipo=tipo,
    )


def _make_formula(insumo, codigo=None):
    global _formula_counter
    _formula_counter += 1
    codigo = codigo or f"F-AUTO-{_formula_counter}"
    return Formula.objects.create(
        insumo=insumo, codigo=codigo, nombre=f"Formula {codigo}",
        expresion="tirada * 1", variables_json=[], version=1, activo=True,
    )


def _make_producto(nombre, formula):
    return Producto.objects.create(
        nombreProducto=nombre, precioUnitario=10,
        activo=True, formula=formula,
    )


def _make_cliente(suffix=""):
    return Cliente.objects.create(
        nombre="Test", apellido="Consumo",
        email=f"consumo{suffix}@test.com",
        telefono="123",
        cuit=f"20-{suffix or '00000000'}-0",
    )


class CalcConsumoProductoTests(TestCase):
    """Tests unitarios de calcular_consumo_producto (services.py)."""

    def setUp(self):
        self.insumo = _make_insumo("Tinta", "TK-01")
        self.formula = _make_formula(self.insumo)
        self.producto = _make_producto("Folleto", self.formula)
        ProductoInsumo.objects.create(
            producto=self.producto, insumo=self.insumo, cantidad_por_unidad=Decimal("3.0")
        )

    def test_consume_bom_estatico(self):
        consumo = calcular_consumo_producto(self.producto, 10)
        self.assertEqual(consumo[self.insumo.idInsumo], Decimal("30"))

    def test_consume_cero_sin_receta(self):
        producto_sin_receta = _make_producto("Sin Receta", self.formula)
        consumo = calcular_consumo_producto(producto_sin_receta, 10)
        self.assertEqual(consumo, {})

    def test_cantidad_cero_retorna_vacio(self):
        consumo = calcular_consumo_producto(self.producto, 0)
        self.assertEqual(consumo, {})

    def test_insumo_costo_fijo_no_multiplica(self):
        ProductoInsumo.objects.filter(producto=self.producto).update(es_costo_fijo=True)
        consumo = calcular_consumo_producto(self.producto, 1000)
        # Fijo: siempre 3, sin importar la cantidad
        self.assertEqual(consumo[self.insumo.idInsumo], Decimal("3.0"))

    def test_multiples_insumos(self):
        insumo2 = _make_insumo("Papel", "PB-02")
        ProductoInsumo.objects.create(
            producto=self.producto, insumo=insumo2, cantidad_por_unidad=Decimal("2.0")
        )
        consumo = calcular_consumo_producto(self.producto, 5)
        self.assertEqual(consumo[self.insumo.idInsumo], Decimal("15"))
        self.assertEqual(consumo[insumo2.idInsumo], Decimal("10"))


class CalcConsumoPedidoTests(TestCase):
    """Tests de calcular_consumo_pedido agregando varias líneas."""

    def setUp(self):
        self.insumo = _make_insumo("Papel Bond", "PB-01")
        formula = _make_formula(self.insumo)
        self.p1 = _make_producto("Tarjeta", formula)
        self.p2 = _make_producto("Afiche", formula)
        ProductoInsumo.objects.create(
            producto=self.p1, insumo=self.insumo, cantidad_por_unidad=Decimal("2.0")
        )
        ProductoInsumo.objects.create(
            producto=self.p2, insumo=self.insumo, cantidad_por_unidad=Decimal("1.0")
        )
        cliente = _make_cliente("pedido1")
        estado, _ = EstadoPedido.objects.get_or_create(nombre="pendiente")
        self.pedido = Pedido.objects.create(
            cliente=cliente,
            fecha_entrega=date.today() + timedelta(days=7),
            monto_total=Decimal("100"),
            estado=estado,
        )
        LineaPedido.objects.create(
            pedido=self.pedido, producto=self.p1, cantidad=3,
            precio_unitario=Decimal("10"),
        )
        LineaPedido.objects.create(
            pedido=self.pedido, producto=self.p2, cantidad=4,
            precio_unitario=Decimal("10"),
        )

    def test_consumo_pedido_agrega_lineas(self):
        # p1: 3*2=6, p2: 4*1=4 → total 10
        consumo = calcular_consumo_pedido(self.pedido)
        self.assertEqual(consumo[self.insumo.idInsumo], Decimal("10"))

    def test_pedido_sin_lineas_retorna_vacio(self):
        estado, _ = EstadoPedido.objects.get_or_create(nombre="vacio")
        cliente = _make_cliente("empty2")
        pedido_vacio = Pedido.objects.create(
            cliente=cliente,
            fecha_entrega=date.today() + timedelta(days=1),
            monto_total=Decimal("0"),
            estado=estado,
        )
        self.assertEqual(calcular_consumo_pedido(pedido_vacio), {})


class VerificarStockLineasTests(TestCase):
    """Tests de verificar_insumos_para_lineas (utils.py)."""

    def setUp(self):
        self.insumo = _make_insumo("Tinta Mix", "TM-01", stock=10)
        formula = _make_formula(self.insumo)
        self.producto = _make_producto("Volante", formula)
        ProductoInsumo.objects.create(
            producto=self.producto, insumo=self.insumo, cantidad_por_unidad=Decimal("2.0")
        )

    def test_stock_suficiente_ok(self):
        ok, faltantes = verificar_insumos_para_lineas([(self.producto, 5)])
        self.assertTrue(ok)
        self.assertEqual(faltantes, {})

    def test_stock_insuficiente_retorna_faltantes(self):
        ok, faltantes = verificar_insumos_para_lineas([(self.producto, 10)])
        # necesita 20, hay 10 → faltan 10
        self.assertFalse(ok)
        self.assertIn(self.insumo.idInsumo, faltantes)
        self.assertAlmostEqual(faltantes[self.insumo.idInsumo], 10.0)

    def test_producto_sin_receta_usa_fallback_stock_total(self):
        """Sin BOM, el fallback valida stock total activo >= cantidad."""
        formula = _make_formula(self.insumo)
        producto_sin_bom = _make_producto("Sin BOM", formula)
        # Stock total activo es 10; pedir 5 debe pasar
        ok, _ = verificar_insumos_para_lineas([(producto_sin_bom, 5)])
        self.assertTrue(ok)
        # Pedir más del stock total disponible debe fallar
        ok2, _ = verificar_insumos_para_lineas([(producto_sin_bom, 9999)])
        self.assertFalse(ok2)


class AjustarInsumosDiferenciaTests(TestCase):
    """Tests de ajustar_insumos_por_diferencia (utils.py)."""

    def setUp(self):
        self.insumo = _make_insumo("Barniz", "BRN-01", stock=50)
        formula = _make_formula(self.insumo, "F-ADJ")
        self.producto = _make_producto("Catálogo", formula)
        ProductoInsumo.objects.create(
            producto=self.producto, insumo=self.insumo, cantidad_por_unidad=Decimal("1.0")
        )

    def test_aumentar_cantidad_descuenta_diferencia(self):
        # old: 5, new: 10 → delta +5 → descuenta 5
        ajustar_insumos_por_diferencia(
            [(self.producto, 5)], [(self.producto, 10)]
        )
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock, 45)

    def test_disminuir_cantidad_repone_diferencia(self):
        # old: 10, new: 6 → delta -4 → repone 4
        ajustar_insumos_por_diferencia(
            [(self.producto, 10)], [(self.producto, 6)]
        )
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock, 54)

    def test_misma_cantidad_no_cambia_stock(self):
        ajustar_insumos_por_diferencia(
            [(self.producto, 7)], [(self.producto, 7)]
        )
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock, 50)

    def test_eliminar_lineas_repone_todo(self):
        # old: 10, new: [] → repone 10
        ajustar_insumos_por_diferencia([(self.producto, 10)], [])
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock, 60)
