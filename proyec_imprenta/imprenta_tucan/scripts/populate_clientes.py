from clientes.models import Cliente
import os
import django
import random
from faker import Faker
from django.db import IntegrityError
from django.core.exceptions import ValidationError

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()


# Crear instancia de Faker con configuración en español
fake = Faker(['es_AR'])


def validar_telefono(numero):
    """Valida que el número de teléfono tenga formato correcto"""
    if not numero or len(numero) < 8:
        raise ValidationError("Número de teléfono inválido")
    return True


def generar_telefono():
    """Genera un número de teléfono argentino válido"""
    codigos_area = ['11', '351', '381', '387', '299']
    codigo = random.choice(codigos_area)
    numero = f"{random.randint(1000, 9999)}{random.randint(1000, 9999)}"
    return f"+54 {codigo} {numero[:4]}-{numero[4:]}"


def crear_cliente():
    """Crea un cliente con datos ficticios y validación"""
    try:
        # Generar datos con variedad para probar ordenamiento
        nombre = fake.first_name()[:50]
        apellido = fake.last_name()[:50]
        telefono = generar_telefono()
        email = f"{nombre.lower()}.{apellido.lower()}@{fake.domain_name()}"
        direccion = fake.street_address()[:200]

        # Validar datos antes de crear
        if not nombre or not apellido:
            raise ValidationError("Nombre y apellido son requeridos")

        validar_telefono(telefono)

        cliente = Cliente.objects.create(
            nombre=nombre,
            apellido=apellido,
            telefono=telefono,
            email=email,
            direccion=direccion
        )

        # Validación completa del modelo
        cliente.full_clean()
        return cliente

    except (IntegrityError, ValidationError) as e:
        print(f"Error de validación: {e}")
        return None


def poblar_base_datos():
    print("Comenzando a generar clientes ficticios...")
    clientes_creados = 0
    intentos = 0
    max_intentos = 120

    while clientes_creados < 100 and intentos < max_intentos:
        cliente = crear_cliente()
        intentos += 1

        if cliente:
            clientes_creados += 1
            print(f"[{clientes_creados}/100] Creado: {cliente.nombre} {cliente.apellido}")

    print(f"\nResumen de la operación:")
    print(f"✓ Clientes creados exitosamente: {clientes_creados}")
    print(f"✓ Intentos realizados: {intentos}")


if __name__ == '__main__':
    try:
        poblar_base_datos()
    except KeyboardInterrupt:
        print("\nOperación cancelada por el usuario")
    except Exception as e:
        print(f"\nError inesperado: {e}")
