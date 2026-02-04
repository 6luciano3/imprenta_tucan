from django.core.management.base import BaseCommand
from django.utils import timezone
from automatizacion.models import ScoreProveedor
from proveedores.models import Proveedor
import random

class Command(BaseCommand):
    help = "Reinicia y crea scores para los primeros 10 proveedores existentes."

    def handle(self, *args, **options):
        ScoreProveedor.objects.all().delete()
        self.stdout.write('Todos los scores eliminados.')
        total = 0
        for proveedor in Proveedor.objects.all()[:10]:
            score_obj, _ = ScoreProveedor.objects.update_or_create(
                proveedor=proveedor,
                defaults={'score': round(random.uniform(60, 100), 2), 'actualizado': timezone.now()}
            )
            self.stdout.write(f"Score creado para Proveedor ID: {proveedor.id}, Nombre: {proveedor.nombre}, Score: {score_obj.score}")
            total += 1
        self.stdout.write(self.style.SUCCESS(f'{total} scores creados para top 10 proveedores.'))
