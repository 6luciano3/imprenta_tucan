from django.core.management.base import BaseCommand
from django.utils import timezone
from proveedores.models import Proveedor
from automatizacion.models import ScoreProveedor

class Command(BaseCommand):
    help = "Crea proveedores de prueba y asigna scores iniciales (descendente por índice)."

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=5, help='Cantidad de proveedores de prueba a crear')
        parser.add_argument('--rubro', type=str, default='Papel', help='Rubro asignado a los proveedores')

    def handle(self, *args, **options):
        count = options['count']
        rubro = options['rubro']
        proveedores = []
        for i in range(1, count + 1):
            proveedor, _ = Proveedor.objects.get_or_create(
                nombre=f"Proveedor Test {i}",
                cuit=f"20-1234567{i}-1",
                email=f"proveedor{i}@test.com",
                telefono=f"381-555-000{i}",
                direccion=f"Calle Falsa {i}00",
                rubro=rubro,
                activo=True
            )
            proveedores.append(proveedor)
        for idx, proveedor in enumerate(proveedores):
            ScoreProveedor.objects.update_or_create(
                proveedor=proveedor,
                defaults={'score': 100 - idx * 10, 'actualizado': timezone.now()}
            )
        self.stdout.write(self.style.SUCCESS('Proveedores y scores de prueba creados correctamente.'))
