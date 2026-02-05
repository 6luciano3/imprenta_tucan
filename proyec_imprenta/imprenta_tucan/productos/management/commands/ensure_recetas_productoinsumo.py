from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Asegura que todos los productos tengan receta definida mediante ProductoInsumo. "
        "Si existe RecetaProducto, se migra a ProductoInsumo (cantidad_por_unidad=1 por defecto). "
        "Como último recurso, usa tinta_insumo del producto si está definida."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        from productos.models import Producto, ProductoInsumo
        from configuracion.models import RecetaProducto
        from insumos.models import Insumo

        creados = 0
        skip_sin_insumo = []

        productos = Producto.objects.all()
        for producto in productos:
            # Si ya tiene receta (al menos un ProductoInsumo), saltar
            if ProductoInsumo.objects.filter(producto=producto).exists():
                continue

            # 1) Intentar migrar desde RecetaProducto (ManyToMany de insumos)
            receta_rel = RecetaProducto.objects.filter(producto=producto, activo=True).prefetch_related('insumos').first()
            if receta_rel and receta_rel.insumos.exists():
                for insumo in receta_rel.insumos.all():
                    ProductoInsumo.objects.get_or_create(
                        producto=producto,
                        insumo=insumo,
                        defaults={"cantidad_por_unidad": 1.0},
                    )
                    creados += 1
                continue

            # 2) Fallback: usar tinta_insumo si está definida
            tinta = getattr(producto, 'tinta_insumo', None)
            if tinta:
                ProductoInsumo.objects.get_or_create(
                    producto=producto,
                    insumo=tinta,
                    defaults={"cantidad_por_unidad": 1.0},
                )
                creados += 1
                continue

            # 3) Último recurso: elegir un insumo activo cualquiera (mejor que dejar sin receta)
            insumo_activo = Insumo.objects.filter(activo=True).order_by('idInsumo').first()
            if insumo_activo:
                ProductoInsumo.objects.get_or_create(
                    producto=producto,
                    insumo=insumo_activo,
                    defaults={"cantidad_por_unidad": 1.0},
                )
                creados += 1
            else:
                skip_sin_insumo.append(producto.idProducto)

        if creados == 0:
            self.stdout.write(self.style.WARNING("No se crearon recetas nuevas; todos los productos ya tenían receta."))
        else:
            self.stdout.write(self.style.SUCCESS(f"ProductoInsumo creados: {creados}"))
        if skip_sin_insumo:
            self.stdout.write(self.style.ERROR(
                f"Productos sin receta por falta de insumos activos: {skip_sin_insumo}"
            ))
