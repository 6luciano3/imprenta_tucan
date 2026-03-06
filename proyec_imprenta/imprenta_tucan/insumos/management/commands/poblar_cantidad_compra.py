"""
Management command: poblar cantidad_compra_sugerida en insumos.

Migra los valores del antiguo diccionario CANTIDADES_COMPRA hardcodeado en
automatizacion/tasks.py al campo Insumo.cantidad_compra_sugerida en la BD.

Uso:
    python manage.py poblar_cantidad_compra [--dry-run]
"""
from django.core.management.base import BaseCommand
from insumos.models import Insumo

# Mapa original hardcodeado en tasks.py (fuente de verdad inicial)
CANTIDADES_COMPRA = {
    'IN-001': 2, 'IN-002': 1, 'IN-003': 1, 'IN-004': 1,
    'IN-042': 1, 'IN-043': 1,
    'TIN-NEGR': 2, 'TIN-CYAN': 1, 'TIN-MAGE': 1, 'TIN-AMAR': 1,
    'IN-018': 1, 'IN-019': 1, 'IN-020': 2, 'BAR-UV-LIQ': 2, 'IN-118': 1,
    'IN-021': 1000, 'IN-022': 500, 'IN-023': 1000, 'IN-024': 5000, 'IN-025': 5000,
    'IN-055': 500, 'IN-056': 1000, 'IN-057': 500, 'IN-071': 2000, 'IN-072': 1000,
    'IN-100': 1000, 'IN-103': 1000, 'IN-104': 500, 'IN-105': 500,
    'IN-106': 5000, 'IN-107': 2000, 'IN-108': 500,
    'PAP-AUT-CON': 2000, 'PAP-ILU-115': 1000, 'PAP-ILU-130': 1000,
    'PAP-ILU-150': 1000, 'PAP-OBR-080': 5000, 'PAP001': 1000,
    'CAR-ILU-250': 500, 'CAR-ILU-300': 500, 'CAR-ILU-350': 500,
    'CAR-GRI-150': 200, 'CAR-GRI-200': 200, 'IN-110': 200, 'IN-111': 200, 'IN-112': 300,
    'IN-101': 1, 'IN-102': 1, 'LAM-BRI-32': 1, 'LAM-MAT-32': 1,
    'PLA-ALU-STD': 50,
    'ENC-ADH-BLO': 5, 'ENC-ESP-MET': 10, 'ENC-GRA-IND': 5, 'ENC-HOT-MEL': 3,
    'IN-113': 3, 'IN-114': 5, 'IN-115': 10, 'IN-116': 10, 'IN-117': 5, 'IN-109': 2,
}


class Command(BaseCommand):
    help = 'Migra CANTIDADES_COMPRA hardcodeadas al campo Insumo.cantidad_compra_sugerida en BD.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra qué se actualizaría sin hacer cambios en la BD.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        actualizados, no_encontrados = 0, []

        for codigo, cantidad in CANTIDADES_COMPRA.items():
            try:
                insumo = Insumo.objects.get(codigo=codigo)
                if dry:
                    self.stdout.write(f'  [dry-run] {codigo} → cantidad_compra_sugerida={cantidad}')
                else:
                    insumo.cantidad_compra_sugerida = cantidad
                    insumo.save(update_fields=['cantidad_compra_sugerida'])
                actualizados += 1
            except Insumo.DoesNotExist:
                no_encontrados.append(codigo)

        if dry:
            self.stdout.write(self.style.WARNING(f'\n[dry-run] Se actualizarían {actualizados} insumos.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✅ {actualizados} insumos actualizados con cantidad_compra_sugerida.'))

        if no_encontrados:
            self.stdout.write(self.style.WARNING(
                f'⚠️  {len(no_encontrados)} códigos no encontrados en BD: {", ".join(no_encontrados)}'
            ))
