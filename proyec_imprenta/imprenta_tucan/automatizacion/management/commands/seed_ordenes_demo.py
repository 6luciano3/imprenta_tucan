from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from automatizacion.models import OrdenSugerida

class Command(BaseCommand):
    help = "Genera datos de demostración para Órdenes sugeridas (y dependencias mínimas)"

    def handle(self, *args, **options):
        from insumos.models import Insumo
        from pedidos.models import Pedido, EstadoPedido
        from clientes.models import Cliente
        from productos.models import Producto
        from configuracion.models import Formula

        created = {"insumo": False, "cliente": False, "estado": False, "formula": False, "producto": False, "pedidos": 0, "ordenes": 0}

        insumo = Insumo.objects.order_by('idInsumo').first()
        if not insumo:
            insumo = Insumo.objects.create(
                nombre="Papel demo",
                codigo="DEMO-001",
                cantidad=100,
                stock=100,
                precio_unitario=Decimal("0"),
                precio=Decimal("0"),
                activo=True,
            )
            created["insumo"] = True

        cliente, ccreated = Cliente.objects.get_or_create(
            email="demo@tucan.local",
            defaults={
                "nombre": "Demo",
                "apellido": "Cliente",
                "razon_social": "Imprenta Tucán",
                "direccion": "Av. Demo 123",
                "ciudad": "Posadas",
                "provincia": "Misiones",
                "pais": "Argentina",
                "telefono": "000000",
                "estado": "Activo",
            },
        )
        created["cliente"] = ccreated

        estado, ecreated = EstadoPedido.objects.get_or_create(nombre="pendiente")
        created["estado"] = ecreated

        formula, fcreated = Formula.objects.get_or_create(
            codigo="DEMO-FORM-001",
            defaults={
                "insumo": insumo,
                "nombre": "Fórmula Demo",
                "descripcion": "Fórmula mínima para producto demo",
                "expresion": "cantidad * 1",
                "variables_json": [],
                "activo": True,
            },
        )
        if formula.insumo_id != insumo.pk:
            formula.insumo = insumo
            formula.save()
        created["formula"] = fcreated

        producto = Producto.objects.order_by('idProducto').first()
        if not producto:
            producto = Producto.objects.create(
                nombreProducto="Producto demo",
                descripcion="Producto de demostración",
                precioUnitario=Decimal("100.00"),
                formula=formula,
            )
            created["producto"] = True

        pedidos = list(Pedido.objects.order_by('-fecha_pedido')[:3])
        if not pedidos:
            pedidos = [
                Pedido.objects.create(
                    cliente=cliente,
                    producto=producto,
                    fecha_entrega=timezone.now().date() + timedelta(days=7),
                    cantidad=10,
                    especificaciones="Pedido demo",
                    monto_total=Decimal("1000.00"),
                    estado=estado,
                )
            ]
            created["pedidos"] = 1
        else:
            created["pedidos"] = len(pedidos)

        cantidades = [5, 10, 15]
        for idx, p in enumerate(pedidos):
            if OrdenSugerida.objects.filter(pedido=p, insumo=insumo).exists():
                continue
            OrdenSugerida.objects.create(
                pedido=p,
                insumo=insumo,
                cantidad=cantidades[idx % len(cantidades)],
            )
            created["ordenes"] += 1

        self.stdout.write(self.style.SUCCESS(f"Demo creado: {created}"))
