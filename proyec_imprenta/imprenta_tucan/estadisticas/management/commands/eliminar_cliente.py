from django.core.management.base import BaseCommand
from clientes.models import Cliente


class Command(BaseCommand):
    help = 'Elimina un cliente por email para pruebas de estadísticas.'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email del cliente a eliminar')

    def handle(self, *args, **options):
        email = options['email']
        try:
            cliente = Cliente.objects.get(email=email)
            cliente.estado = 'Inactivo'
            cliente.save()
            self.stdout.write(self.style.SUCCESS(f'Cliente con email {email} desactivado correctamente.'))
        except Cliente.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'No existe un cliente con email {email}.'))
