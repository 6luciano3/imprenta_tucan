from django.core.management.base import BaseCommand

try:
    from automatizacion.tasks import tarea_ranking_clientes
except Exception:
    tarea_ranking_clientes = None

class Command(BaseCommand):
    help = "Genera/actualiza el ranking dinámico de clientes estratégicos"

    def handle(self, *args, **options):
        if tarea_ranking_clientes is None:
            self.stdout.write(self.style.ERROR("No se pudo importar la tarea de ranking."))
            return
        try:
            # Ejecuta síncronamente
            resultado = tarea_ranking_clientes()
            self.stdout.write(self.style.SUCCESS(str(resultado)))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
