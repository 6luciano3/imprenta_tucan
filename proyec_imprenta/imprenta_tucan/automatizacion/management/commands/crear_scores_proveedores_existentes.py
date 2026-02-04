from django.core.management.base import BaseCommand
from django.utils import timezone
from automatizacion.models import ScoreProveedor
from proveedores.models import Proveedor
import random

class Command(BaseCommand):
    help = "Crea/actualiza scores aleatorios para todos los proveedores existentes."

    def add_arguments(self, parser):
        parser.add_argument('--min', type=float, default=60.0, help='Score mínimo')
        parser.add_argument('--max', type=float, default=100.0, help='Score máximo')

    def handle(self, *args, **options):
        min_score = options['min']
        max_score = options['max']
        count = 0
        for proveedor in Proveedor.objects.all():
            score_val = round(random.uniform(min_score, max_score), 2)
            ScoreProveedor.objects.update_or_create(
                proveedor=proveedor,
                defaults={'score': score_val, 'actualizado': timezone.now()}
            )
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Scores de prueba creados/actualizados para {count} proveedores.'))
