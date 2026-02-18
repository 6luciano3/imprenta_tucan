from django.core.management.base import BaseCommand
from insumos.models import Insumo

class Command(BaseCommand):
    help = 'Lista todos los insumos sin proveedor asignado.'

    def handle(self, *args, **options):
        sin_proveedor = Insumo.objects.filter(proveedor__isnull=True)
        total = sin_proveedor.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('Todos los insumos tienen proveedor asignado.'))
        else:
            self.stdout.write(self.style.WARNING(f'Hay {total} insumos sin proveedor asignado:'))
            for insumo in sin_proveedor:
                self.stdout.write(f'- {insumo.nombre} (Código: {insumo.codigo})')
