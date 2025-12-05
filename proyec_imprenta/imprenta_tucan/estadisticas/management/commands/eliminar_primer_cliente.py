from django.core.management.base import BaseCommand
from clientes.models import Cliente


class Command(BaseCommand):
    help = 'Elimina automáticamente el primer cliente encontrado para pruebas de estadísticas.'

    def handle(self, *args, **options):
        cliente = Cliente.objects.first()
        if cliente:
            email = cliente.email
            cliente.delete()
            self.stdout.write(self.style.SUCCESS(f'Cliente con email {email} eliminado correctamente.'))
        else:
            self.stdout.write(self.style.ERROR('No hay clientes para eliminar.'))
