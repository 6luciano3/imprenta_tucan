from django.db import connection, transaction
from automatizacion.models import ScoreProveedor
from django.utils import timezone
import random

nombres = [
    'Proveedor Alfa', 'Proveedor Beta', 'Proveedor Gamma', 'Proveedor Delta', 'Proveedor Epsilon',
    'Proveedor Zeta', 'Proveedor Eta', 'Proveedor Theta', 'Proveedor Iota', 'Proveedor Kappa'
]

with transaction.atomic():
    for i, nombre in enumerate(nombres):
        cuit = f"20-1234567{i}-1"
        email = f'{nombre.lower().replace(" ", "_")}@mail.com'
        telefono = f'381-{1000+i}'
        direccion = f'Calle Falsa {i+1}'
        rubro = 'General'
        fecha = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        apellido = f"Apellido{i+1}"
        empresa = f"Empresa{i+1}"
        # Insertar proveedor vía SQL directo
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO proveedores_proveedor (nombre, cuit, email, telefono, direccion, rubro, fecha_creacion, activo, apellido, empresa) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [nombre, cuit, email, telefono, direccion, rubro, fecha, 1, apellido, empresa]
            )
            proveedor_id = cursor.lastrowid
        # Crear score para el proveedor
        score = round(random.uniform(50, 100), 2)
        ScoreProveedor.objects.create(
            proveedor_id=proveedor_id,
            score=score,
            actualizado=timezone.now()
        )
print('Proveedores y scores de prueba creados con SQL directo.')
