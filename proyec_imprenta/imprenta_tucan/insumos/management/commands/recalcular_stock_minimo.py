"""
Tarea programada: pre-calcula stock_minimo_sugerido para cada insumo activo
y guarda el resultado en stock_minimo_calculado, evitando queries N+1 en listados.

Uso:
    python manage.py recalcular_stock_minimo
    python manage.py recalcular_stock_minimo --verbosity 2   # detallado
"""
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Pre-calcula stock_minimo_sugerido para cada insumo activo y lo guarda en stock_minimo_calculado."

    def add_arguments(self, parser):
        parser.add_argument(
            '--solo-activos',
            action='store_true',
            default=True,
            help='Procesar únicamente insumos activos (default: True).',
        )

    def handle(self, *args, **options):
        from insumos.models import Insumo
        try:
            from configuracion.models import Parametro
            dias_reposicion = int(Parametro.get('DIAS_REPOSICION_INSUMO', 15))
        except Exception:
            dias_reposicion = 15

        qs = Insumo.objects.filter(activo=True)
        total = qs.count()
        actualizados = 0
        errores = 0

        self.stdout.write(f"Recalculando stock mínimo para {total} insumos activos (días de reposición: {dias_reposicion})...")

        for insumo in qs.iterator():
            try:
                # Temporalmente nullear el campo para forzar el cálculo en tiempo real
                # (evita que la property devuelva el valor cacheado anterior)
                insumo.stock_minimo_calculado = None
                valor = insumo.stock_minimo_sugerido
                insumo.stock_minimo_calculado = valor
                insumo.save(update_fields=['stock_minimo_calculado'])
                actualizados += 1
                if options['verbosity'] >= 2:
                    self.stdout.write(f"  [{insumo.codigo}] {insumo.nombre}: {valor}")
            except Exception as e:
                errores += 1
                logger.exception("recalcular_stock_minimo: error en insumo #%s", insumo.pk)
                if options['verbosity'] >= 1:
                    self.stderr.write(f"  ERROR en [{insumo.codigo}]: {e}")

        resumen = f"Completado: {actualizados}/{total} actualizados"
        if errores:
            resumen += f", {errores} errores"
        self.stdout.write(self.style.SUCCESS(resumen))
        logger.info("recalcular_stock_minimo: %s", resumen)
