from datetime import date, timedelta

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from insumos.models import Insumo
from pedidos.models import Pedido, EstadoPedido
from productos.models import Producto, UnidadMedida, ProductoInsumo


class AltaPedidoTests(TestCase):
    def setUp(self):
        # Datos comunes
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
        )

        self.um = UnidadMedida.objects.create(nombreUnidad="Unidad", abreviatura="u")

        # Insumo único para simplificar recetas
        self.insumo = Insumo.objects.create(
            nombre="Papel A4",
            codigo="PAP-A4",
            cantidad=1000,
            precio_unitario=Decimal("10.00"),
            categoria="Papel",
            stock=0,  # se definirá por test
            precio=Decimal("10.00"),
            activo=True,
        )

        # Productos
        self.p1 = Producto.objects.create(
            nombreProducto="Tarjeta",
            descripcion="",
            precioUnitario=Decimal("100.00"),
            unidadMedida=self.um,
            activo=True,
        )
        self.p2 = Producto.objects.create(
            nombreProducto="Folleto",
            descripcion="",
            precioUnitario=Decimal("50.00"),
            unidadMedida=self.um,
            activo=True,
        )

        # Recetas: cantidad_por_unidad
        ProductoInsumo.objects.create(producto=self.p1, insumo=self.insumo, cantidad_por_unidad=Decimal("2.0"))
        ProductoInsumo.objects.create(producto=self.p2, insumo=self.insumo, cantidad_por_unidad=Decimal("1.0"))

        self.url_alta = reverse("alta_pedido")

    def _post_form(self, lineas, aplicar_iva=False):
        """Helper para enviar el formulario de alta con N líneas.
        lineas: lista de tuplas (producto_id, cantidad)
        """
        payload = {
            "cliente": str(self.cliente.id),
            "fecha_entrega": (date.today() + timedelta(days=1)).isoformat(),
        }
        if aplicar_iva:
            # Checkbox marcado
            payload["aplicar_iva"] = "on"

        total_forms = len(lineas)
        payload.update(
            {
                "lineas-TOTAL_FORMS": str(total_forms),
                "lineas-INITIAL_FORMS": "0",
                "lineas-MIN_NUM_FORMS": "0",
                "lineas-MAX_NUM_FORMS": "1000",
            }
        )
        for idx, (pid, cant) in enumerate(lineas):
            payload[f"lineas-{idx}-producto"] = str(pid)
            payload[f"lineas-{idx}-cantidad"] = str(cant)
            payload[f"lineas-{idx}-especificaciones"] = ""

        return self.client.post(self.url_alta, data=payload, follow=False)

    def test_alta_pedido_happy_path_crea_varias_lineas_y_descuenta_stock(self):
        # Stock suficiente: p1 necesita 2 por unidad, p2 1 por unidad
        # Pedimos 3 de p1 y 4 de p2 => requeridos = (3*2) + (4*1) = 10
        self.insumo.stock = 15
        self.insumo.save()

        resp = self._post_form([(self.p1.pk, 3), (self.p2.pk, 4)], aplicar_iva=False)

        # Debe redirigir a lista (201/302)
        self.assertIn(resp.status_code, (301, 302))
        self.assertEqual(Pedido.objects.count(), 2)

        pedidos = list(Pedido.objects.order_by("id"))
        self.assertEqual(pedidos[0].producto_id, self.p1.pk)
        self.assertEqual(pedidos[0].cantidad, 3)
        self.assertEqual(pedidos[0].monto_total, Decimal("300.00"))  # 100 * 3
        self.assertEqual(pedidos[1].producto_id, self.p2.pk)
        self.assertEqual(pedidos[1].cantidad, 4)
        self.assertEqual(pedidos[1].monto_total, Decimal("200.00"))  # 50 * 4

        # Estado inicial debe ser Pendiente
        self.assertTrue(EstadoPedido.objects.filter(nombre="Pendiente").exists())

        # Stock descontado en base a recetas: 10 usados
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock, 5)

    def test_alta_pedido_con_iva_aplica_multiplier_por_linea(self):
        # Stock suficiente para 1 unidad de p1
        self.insumo.stock = 5
        self.insumo.save()

        resp = self._post_form([(self.p1.pk, 1)], aplicar_iva=True)
        self.assertIn(resp.status_code, (301, 302))
        pedido = Pedido.objects.latest("id")
        # 100 * 1 * 1.21 = 121.00
        self.assertEqual(pedido.monto_total, Decimal("121.00"))

    def test_alta_pedido_falla_por_stock_insuficiente_no_crea_pedidos(self):
        # Requeridos: 3 de p1 => 6 insumos; hay 5
        self.insumo.stock = 5
        self.insumo.save()

        resp = self._post_form([(self.p1.pk, 3)], aplicar_iva=False)
        # Debe quedarse en la página (200) y mostrar error en contenido
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertContains(resp, "No hay insumos suficientes", status_code=200)
