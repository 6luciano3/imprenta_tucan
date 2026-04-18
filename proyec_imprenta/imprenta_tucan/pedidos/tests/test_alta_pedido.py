from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from configuracion.models import Formula, UnidadDeMedida
from insumos.models import Insumo
from pedidos.models import EstadoPedido, LineaPedido, Pedido
from productos.models import CategoriaProducto, Producto, ProductoInsumo, TipoProducto
from usuarios.models import Usuario


class AltaPedidoTests(TestCase):
    def setUp(self):
        from roles.models import Rol
        from permisos.models import Permiso
        import json as _json

        permiso = Permiso.objects.create(
            nombre="Permiso Pedidos",
            descripcion="Permite crear pedidos",
            modulo="Pedidos",
            acciones=_json.dumps(["Listar", "Crear", "Ver", "Editar", "Eliminar"]),
            estado="Activo",
        )
        rol = Rol.objects.create(nombreRol="Rol Test Pedidos", estado="Activo")
        rol.permisos.add(permiso)
        self.user = Usuario.objects.create_user(
            email="pedidostest@test.com",
            password="testpass",
            nombre="Test",
            apellido="Pedidos",
            telefono="1234",
            rol=rol,
        )
        self.client.force_login(self.user)

        self.cliente = Cliente.objects.create(
            nombre="Juan",
            apellido="Pérez",
            razon_social="JP SRL",
            direccion="Calle 123",
            ciudad="Posadas",
            provincia="Misiones",
            pais="Argentina",
            telefono="123456",
            email="juan@example.com",
            cuit="20-11111111-1",
        )
        EstadoPedido.objects.get_or_create(nombre="Pendiente")

        self.insumo = Insumo.objects.create(
            nombre="Papel A4",
            codigo="PAP-A4",
            precio_unitario=Decimal("10.00"),
            categoria="Papel",
            stock=50,
            activo=True,
        )
        self.formula = Formula.objects.create(
            insumo=self.insumo,
            codigo="F001",
            nombre="Formula Test",
            expresion="tirada * 1",
            variables_json=[],
            version=1,
            activo=True,
        )
        self.p1 = Producto.objects.create(
            nombreProducto="Tarjeta",
            precioUnitario=Decimal("100.00"),
            activo=True,
            formula=self.formula,
        )
        self.p2 = Producto.objects.create(
            nombreProducto="Folleto",
            precioUnitario=Decimal("50.00"),
            activo=True,
            formula=self.formula,
        )
        ProductoInsumo.objects.create(
            producto=self.p1, insumo=self.insumo, cantidad_por_unidad=Decimal("2.0")
        )
        ProductoInsumo.objects.create(
            producto=self.p2, insumo=self.insumo, cantidad_por_unidad=Decimal("1.0")
        )

    def _post_alta(self, lineas, aplicar_iva=False, descuento=0):
        """lineas: lista de tuplas (producto_id, cantidad)."""
        payload = {
            "cliente": str(self.cliente.id),
            "fecha_entrega": (date.today() + timedelta(days=7)).isoformat(),
            "descuento": str(descuento),
            "lineas-TOTAL_FORMS": str(len(lineas)),
            "lineas-INITIAL_FORMS": "0",
            "lineas-MIN_NUM_FORMS": "0",
            "lineas-MAX_NUM_FORMS": "1000",
        }
        if aplicar_iva:
            payload["aplicar_iva"] = "on"
        for idx, (pid, cant) in enumerate(lineas):
            payload[f"lineas-{idx}-producto"] = str(pid)
            payload[f"lineas-{idx}-cantidad"] = str(cant)
            payload[f"lineas-{idx}-especificaciones"] = ""
        return self.client.post(reverse("alta_pedido"), data=payload)

    def test_alta_pedido_crea_un_pedido_con_multiples_lineas(self):
        resp = self._post_alta([(self.p1.pk, 3), (self.p2.pk, 4)])
        self.assertIn(resp.status_code, (301, 302))

        self.assertEqual(Pedido.objects.count(), 1)
        pedido = Pedido.objects.first()
        self.assertEqual(pedido.cliente, self.cliente)
        self.assertEqual(pedido.estado.nombre, "Pendiente")

        lineas = list(pedido.lineas.order_by("producto__nombreProducto"))
        self.assertEqual(len(lineas), 2)
        self.assertEqual(lineas[0].producto, self.p2)  # Folleto
        self.assertEqual(lineas[0].cantidad, 4)
        self.assertEqual(lineas[1].producto, self.p1)  # Tarjeta
        self.assertEqual(lineas[1].cantidad, 3)

    def test_alta_pedido_calcula_monto_total_correctamente(self):
        # 3 * 100 + 4 * 50 = 500
        resp = self._post_alta([(self.p1.pk, 3), (self.p2.pk, 4)])
        self.assertIn(resp.status_code, (301, 302))
        pedido = Pedido.objects.first()
        self.assertEqual(pedido.monto_total, Decimal("500.00"))

    def test_alta_pedido_aplica_iva(self):
        # 1 * 100 * 1.21 = 121
        resp = self._post_alta([(self.p1.pk, 1)], aplicar_iva=True)
        self.assertIn(resp.status_code, (301, 302))
        pedido = Pedido.objects.first()
        self.assertEqual(pedido.monto_total, Decimal("121.00"))

    def test_alta_pedido_aplica_descuento(self):
        # 1 * 100 con 10% descuento = 90
        resp = self._post_alta([(self.p1.pk, 1)], descuento=10)
        self.assertIn(resp.status_code, (301, 302))
        pedido = Pedido.objects.first()
        self.assertEqual(pedido.monto_total, Decimal("90.00"))

    def test_alta_pedido_no_descuenta_stock_en_creacion(self):
        """Stock sólo se descuenta al pasar a 'proceso', no al crear en Pendiente."""
        stock_antes = self.insumo.stock
        self._post_alta([(self.p1.pk, 3)])
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock, stock_antes)

    def test_alta_pedido_sin_lineas_muestra_error(self):
        payload = {
            "cliente": str(self.cliente.id),
            "fecha_entrega": (date.today() + timedelta(days=7)).isoformat(),
            "descuento": "0",
            "lineas-TOTAL_FORMS": "0",
            "lineas-INITIAL_FORMS": "0",
            "lineas-MIN_NUM_FORMS": "0",
            "lineas-MAX_NUM_FORMS": "1000",
        }
        resp = self.client.post(reverse("alta_pedido"), data=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertContains(resp, "al menos un producto")


class CambioEstadoStockTests(TestCase):
    """Verifica que el stock se descuenta al pasar el pedido a estado 'proceso'."""

    def setUp(self):
        self.insumo = Insumo.objects.create(
            nombre="Tinta Negra", codigo="INK-001",
            stock=100, precio_unitario=10, activo=True,
        )
        formula = Formula.objects.create(
            insumo=self.insumo, codigo="F-ST", nombre="Formula Stock",
            expresion="tirada * 1", variables_json=[], version=1, activo=True,
        )
        self.producto = Producto.objects.create(
            nombreProducto="Tarjeta Stock",
            precioUnitario=50, activo=True, formula=formula,
        )
        ProductoInsumo.objects.create(
            producto=self.producto, insumo=self.insumo, cantidad_por_unidad=2
        )
        self.cliente = Cliente.objects.create(
            nombre="Stock", apellido="Test",
            email="stock@test.com", telefono="123456",
            cuit="20-22222222-2",
        )
        self.estado_pendiente, _ = EstadoPedido.objects.get_or_create(nombre="pendiente")
        self.estado_proceso, _ = EstadoPedido.objects.get_or_create(nombre="proceso")

    def _crear_pedido_con_lineas(self, cantidad):
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

    def test_cambio_a_proceso_descuenta_stock(self):
        pedido = self._crear_pedido_con_lineas(10)
        stock_antes = self.insumo.stock

        pedido.estado = self.estado_proceso
        pedido.save()

        self.insumo.refresh_from_db()
        # 10 unidades * 2 por unidad = 20
        self.assertEqual(self.insumo.stock, stock_antes - 20)

    def test_cambio_sin_proceso_no_descuenta_stock(self):
        pedido = self._crear_pedido_con_lineas(10)
        stock_antes = self.insumo.stock

        estado_entregado, _ = EstadoPedido.objects.get_or_create(nombre="entregado")
        pedido.estado = estado_entregado
        pedido.save()

        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock, stock_antes)

    def test_cambio_a_proceso_stock_insuficiente_lanza_error(self):
        self.insumo.stock = 5  # necesita 20
        self.insumo.save()

        pedido = self._crear_pedido_con_lineas(10)

        pedido.estado = self.estado_proceso
        with self.assertRaises(ValueError):
            pedido.save()
