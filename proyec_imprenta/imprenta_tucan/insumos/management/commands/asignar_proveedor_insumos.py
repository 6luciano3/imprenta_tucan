from django.core.management.base import BaseCommand
from insumos.models import Insumo
from proveedores.models import Proveedor

class Command(BaseCommand):
    help = 'Asigna proveedores automáticamente a insumos sin proveedor. Usa el primer proveedor disponible.'

    def handle(self, *args, **options):
        sin_proveedor = Insumo.objects.filter(proveedor__isnull=True)
        total = sin_proveedor.count()
        proveedor = Proveedor.objects.filter(activo=True).order_by('id').first()
        if not proveedor:
            self.stdout.write(self.style.ERROR('No hay proveedores activos disponibles.'))
            return
        if total == 0:
            self.stdout.write(self.style.SUCCESS('Todos los insumos ya tienen proveedor asignado.'))
            return
        for insumo in sin_proveedor:
            insumo.proveedor = proveedor
            insumo.save()
            self.stdout.write(f'Asignado proveedor "{proveedor}" a insumo: {insumo.nombre} (Código: {insumo.codigo})')
        self.stdout.write(self.style.SUCCESS(f'Se asignó el proveedor "{proveedor}" a {total} insumos.'))
