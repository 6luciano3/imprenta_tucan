from django.core.management.base import BaseCommand


from importlib import import_module
tarea_ranking_clientes = None
try:
    # Importación robusta compatible con ejecución como comando Django
    tasks_mod = import_module('automatizacion.tasks')
    tarea_ranking_clientes = getattr(tasks_mod, 'tarea_ranking_clientes', None)
except Exception as e:
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
