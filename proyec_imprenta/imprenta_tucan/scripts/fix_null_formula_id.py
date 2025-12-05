

import os
import sys
import django
from django.db import connection

# Agregar la ruta raíz del proyecto al sys.path
PROJECT_ROOT = r'C:\Users\Public\Documents\facultad\3er Año\Trabajo Final\proyecto_imprenta'
APP_ROOT = os.path.join(PROJECT_ROOT, 'proyec_imprenta', 'imprenta_tucan')
for path in [PROJECT_ROOT, APP_ROOT]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Inicializar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyec_imprenta.imprenta_tucan.impre_tucan.settings')
django.setup()

# Este script asigna un formula_id válido a los productos que lo tengan en NULL
# Reemplaza 1 por el ID de una fórmula válida existente en tu base de datos
FORMULA_ID_DEFAULT = 1

with connection.cursor() as cursor:
    cursor.execute(
        "UPDATE productos_producto SET formula_id = %s WHERE formula_id IS NULL",
        [FORMULA_ID_DEFAULT]
    )
print("Actualización completada. Los productos sin fórmula ahora tienen formula_id =", FORMULA_ID_DEFAULT)
