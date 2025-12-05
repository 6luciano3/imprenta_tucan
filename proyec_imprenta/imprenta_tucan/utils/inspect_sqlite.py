import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()

with connection.cursor() as cursor:
    cursor.execute("PRAGMA table_info('proveedores_proveedor')")
    cols = cursor.fetchall()
    print('Tabla proveedores_proveedor - columnas:')
    for col in cols:
        print(col)
