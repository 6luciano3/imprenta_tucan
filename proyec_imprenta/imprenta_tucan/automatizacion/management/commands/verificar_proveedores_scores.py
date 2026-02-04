from django.core.management.base import BaseCommand
from automatizacion.models import ScoreProveedor
from proveedores.models import Proveedor

class Command(BaseCommand):
    help = "Verifica la existencia de proveedores y lista scores asociados."

    def handle(self, *args, **options):
        self.stdout.write('Proveedores existentes:')
        for p in Proveedor.objects.all():
            self.stdout.write(f"ID: {p.id}, Nombre: {p.nombre}")
        self.stdout.write('\nScores existentes:')
        for s in ScoreProveedor.objects.all():
            self.stdout.write(f"ID: {s.id}, Proveedor ID: {s.proveedor_id}, Score: {s.score}")
