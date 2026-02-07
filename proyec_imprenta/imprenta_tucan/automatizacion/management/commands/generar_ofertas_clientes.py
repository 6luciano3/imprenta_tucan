from django.core.management.base import BaseCommand

try:
    from automatizacion.tasks import tarea_generar_ofertas
except Exception:
    tarea_generar_ofertas = None

class Command(BaseCommand):
    help = "Genera propuestas automáticas de ofertas para clientes estratégicos"

    def handle(self, *args, **options):
        if tarea_generar_ofertas is None:
            self.stdout.write(self.style.ERROR("No se pudo importar la tarea de ofertas."))
            return
        try:
            resultado = tarea_generar_ofertas()
            self.stdout.write(self.style.SUCCESS(str(resultado)))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
