from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decimal import Decimal

from pedidos.models import Pedido
from productos.models import Producto, ProductoInsumo
from insumos.models import Insumo
from pedidos.utils import (
    verificar_insumos_para_ajuste,
    ajustar_insumos_por_diferencia,
)


class Command(BaseCommand):
    help = "Smoke test: modifica un pedido ajustando stock por diferencia (descuento/reposición)."

    def add_arguments(self, parser):
        parser.add_argument("--pedido", type=int, help="ID del Pedido a modificar")
        parser.add_argument("--producto", type=int, help="Nuevo ID de Producto (opcional)", nargs="?")
        parser.add_argument("--cantidad", type=int, help="Nueva cantidad (opcional)", nargs="?")
        parser.add_argument("--delta", type=int, help="Ajuste relativo de cantidad (suma al valor actual)", nargs="?")

    def handle(self, *args, **options):
        pedido_id = options.get("pedido")
        producto_id = options.get("producto")
        cantidad = options.get("cantidad")
        delta = options.get("delta")

        pedido = None
        if pedido_id:
            try:
                pedido = Pedido.objects.select_related("producto").get(pk=pedido_id)
            except Pedido.DoesNotExist:
                raise CommandError(f"Pedido id={pedido_id} no existe")
        else:
            pedido = Pedido.objects.select_related("producto").order_by("id").first()
            if not pedido:
                raise CommandError("No hay pedidos en la base para probar")
            self.stdout.write(self.style.WARNING(f"Usando Pedido id={pedido.id} por defecto"))

        new_producto = pedido.producto
        if producto_id:
            try:
                new_producto = Producto.objects.get(pk=producto_id)
            except Producto.DoesNotExist:
                raise CommandError(f"Producto id={producto_id} no existe")

        if cantidad is not None:
            new_cantidad = cantidad
        elif delta is not None:
            new_cantidad = (pedido.cantidad or 0) + int(delta)
            if new_cantidad < 0:
                new_cantidad = 0
        else:
            new_cantidad = pedido.cantidad

        self.stdout.write(
            f"Pedido actual: id={pedido.id}, producto={pedido.producto} (id={pedido.producto_id}), cantidad={pedido.cantidad}")
        self.stdout.write(
            f"Nuevo estado:  producto={new_producto} (id={new_producto.idProducto}), cantidad={new_cantidad}")

        # Determinar insumos relevantes (union de recetas vieja y nueva)
        insumos_old = list(ProductoInsumo.objects.filter(producto=pedido.producto).values_list("insumo_id", flat=True))
        insumos_new = list(ProductoInsumo.objects.filter(producto=new_producto).values_list("insumo_id", flat=True))
        relevantes = set(insumos_old) | set(insumos_new)

        stocks_antes = {i.idInsumo: i.stock for i in Insumo.objects.filter(idInsumo__in=relevantes)}

        # Validar ajuste neto
        ok, faltantes = verificar_insumos_para_ajuste(
            [(pedido.producto, pedido.cantidad)], [(new_producto, new_cantidad)])
        if not ok:
            detalle = ", ".join([f"{iid}: faltan {falt:.2f}" for iid, falt in faltantes.items()])
            raise CommandError(f"Faltan insumos para el ajuste: {detalle}")

        # Aplicar ajuste y guardar pedido
        with transaction.atomic():
            ajustar_insumos_por_diferencia([(pedido.producto, pedido.cantidad)], [(new_producto, new_cantidad)])

            pedido.producto = new_producto
            pedido.cantidad = new_cantidad
            pedido.monto_total = (new_producto.precio or Decimal("0")) * Decimal(new_cantidad or 0)
            pedido.save(update_fields=["producto", "cantidad", "monto_total"])

        stocks_despues = {i.idInsumo: i.stock for i in Insumo.objects.filter(idInsumo__in=relevantes)}

        # Mostrar delta por insumo
        self.stdout.write(self.style.SUCCESS("Ajuste aplicado. Cambios en stock:"))
        if not relevantes:
            self.stdout.write("(Sin recetas asociadas; no hubo cambios de stock)")
        for iid in sorted(relevantes):
            antes = stocks_antes.get(iid, 0)
            despues = stocks_despues.get(iid, 0)
            delta = despues - antes
            try:
                ins = Insumo.objects.get(pk=iid)
                etiqueta = f"{ins.codigo} - {ins.nombre}"
            except Insumo.DoesNotExist:
                etiqueta = f"Insumo {iid}"
            self.stdout.write(f"  {etiqueta}: {antes} -> {despues} (Δ {delta})")

        self.stdout.write(self.style.SUCCESS("Smoke test finalizado"))
