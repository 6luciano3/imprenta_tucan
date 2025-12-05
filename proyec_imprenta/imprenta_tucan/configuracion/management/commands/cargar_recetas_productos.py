from django.core.management.base import BaseCommand
from productos.models import Producto
from configuracion.models import Formula, RecetaProducto
from insumos.models import Insumo


class Command(BaseCommand):
    help = 'Carga recetas de productos usando fórmulas e insumos ya existentes.'

    def handle(self, *args, **options):
        productos = Producto.objects.all()
        formulas = Formula.objects.all()
        insumos = Insumo.objects.all()
        count = 0
        for producto in productos:
            # Buscar fórmula por nombre/código relacionado al producto
            formula = formulas.filter(nombre__icontains=producto.nombreProducto).first()
            if not formula:
                continue
            # Buscar insumos relacionados por nombre/categoría
            insumos_rel = insumos.filter(categoria__icontains=producto.nombreProducto)
            receta, created = RecetaProducto.objects.get_or_create(
                producto=producto,
                formula=formula,
                defaults={"descripcion": f"Receta auto-generada para {producto.nombreProducto}"}
            )
            if created:
                receta.insumos.set(insumos_rel)
                receta.save()
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Recetas creadas/actualizadas: {count}"))
