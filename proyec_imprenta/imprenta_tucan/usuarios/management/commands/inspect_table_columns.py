from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Lista las columnas de una tabla SQLite (PRAGMA table_info)"

    def add_arguments(self, parser):
        parser.add_argument('--table', type=str, required=True, help='Nombre de la tabla (por ejemplo, clientes_cliente)')

    def handle(self, *args, **options):
        table = options['table']
        cursor = connection.cursor()
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            rows = cursor.fetchall()
        except Exception as e:
            raise CommandError(f"Error consultando tabla '{table}': {e}")

        if not rows:
            self.stdout.write(self.style.WARNING(f"La tabla '{table}' no existe o no tiene columnas."))
            return

        columns = [row[1] for row in rows]
        self.stdout.write(self.style.SUCCESS(f"Tabla: {table}\nColumnas: {columns}"))
