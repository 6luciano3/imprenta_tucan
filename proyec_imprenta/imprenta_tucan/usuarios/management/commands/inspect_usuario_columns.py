from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Lista las columnas de la tabla usuarios_usuario"

    def handle(self, *args, **options):
        cursor = connection.cursor()
        cursor.execute('PRAGMA table_info(usuarios_usuario)')
        columns = [row[1] for row in cursor.fetchall()]
        self.stdout.write(self.style.SUCCESS(f"Columnas: {columns}"))
