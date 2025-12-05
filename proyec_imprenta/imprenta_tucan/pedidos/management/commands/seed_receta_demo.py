from django.core.management.base import BaseCommand, CommandError
from decimal import Decimal

from pedidos.models import Pedido
from productos.models import Producto, ProductoInsumo
from insumos.models import Insumo


class Command(BaseCommand):
    help = "Crea/actualiza una receta (ProductoInsumo) para el producto de un pedido y asegura stock suficiente para demo."

    def add_arguments(self, parser):
        parser.add_argument("--pedido", type=int, help="ID del Pedido base (opcional)", nargs="?")
        parser.add_argument("--producto", type=int,
                            help="ID del Producto (opcional; por defecto, del Pedido)", nargs="?")
        parser.add_argument("--insumo", type=int, help="ID del Insumo a usar en la receta (opcional)", nargs="?")
        parser.add_argument("--cantidad_por_unidad", type=str, default="2.0",
                            help="Cantidad de insumo por unidad de producto")
        parser.add_argument("--stock_minimo", type=int, default=1000, help="Stock mínimo a garantizar en el insumo")

    def handle(self, *args, **options):
        pedido_id = options.get("pedido")
        producto_id = options.get("producto")
        insumo_id = options.get("insumo")
        cantidad_por_unidad = Decimal(options.get("cantidad_por_unidad") or "2.0")
        stock_minimo = int(options.get("stock_minimo") or 1000)

        pedido = None
        if pedido_id:
            try:
                pedido = Pedido.objects.select_related("producto").get(pk=pedido_id)
            except Pedido.DoesNotExist:
                raise CommandError(f"Pedido id={pedido_id} no existe")
        else:
            pedido = Pedido.objects.select_related("producto").order_by("id").first()
            if not pedido and not producto_id:
                raise CommandError("No hay pedidos y no se especificó --producto")

        if producto_id:
            try:
                producto = Producto.objects.get(pk=producto_id)
            except Producto.DoesNotExist:
                raise CommandError(f"Producto id={producto_id} no existe")
        else:
            producto = pedido.producto if pedido else Producto.objects.order_by("idProducto").first()
            if not producto:
                raise CommandError("No hay productos en la base")

        if insumo_id:
            try:
                insumo = Insumo.objects.get(pk=insumo_id)
            except Insumo.DoesNotExist:
                raise CommandError(f"Insumo id={insumo_id} no existe")
        else:
            insumo = Insumo.objects.order_by("idInsumo").first()
            if not insumo:
                raise CommandError("No hay insumos en la base")

        # Crear o actualizar receta
        obj, created = ProductoInsumo.objects.update_or_create(
            producto=producto,
            insumo=insumo,
            defaults={"cantidad_por_unidad": cantidad_por_unidad},
        )

        # Asegurar stock mínimo
        if insumo.stock < stock_minimo:
            antes = insumo.stock
            insumo.stock = stock_minimo
            insumo.save(update_fields=["stock", "updated_at"]) if hasattr(
                insumo, "updated_at") else insumo.save(update_fields=["stock"])  # fallback
            self.stdout.write(self.style.WARNING(
                f"Stock de {insumo.codigo} elevado de {antes} a {insumo.stock} para la demo"))

        self.stdout.write(self.style.SUCCESS(
            f"Receta {'creada' if created else 'actualizada'}: {producto} <- {insumo} x {cantidad_por_unidad}"
        ))
