from pedidos.models import Pedido, EstadoPedido
from productos.models import Producto
from clientes.models import Cliente
from django.utils import timezone
from django.db import transaction
import os
import django
import random
from datetime import timedelta, date
from decimal import Decimal

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()


ESTADOS = [
    "Pendiente",
    "En Proceso",
    "Completado",
    "Cancelado",
]


def ensure_estados():
    for nombre in ESTADOS:
        EstadoPedido.objects.get_or_create(nombre=nombre)


def ensure_productos_y_clientes(min_clientes: int = 50):
    # Productos
    if Producto.objects.count() == 0:
        try:
            # Intentar cargar catálogo base si existe el script
            from populate_productos import cargar_productos
            creados, actualizados = cargar_productos()
            print(f"Productos cargados. Creados: {creados}, actualizados: {actualizados}")
        except Exception as e:
            print(f"No se pudo cargar productos automáticamente: {e}")

    # Clientes
    existentes = Cliente.objects.count()
    a_crear = max(0, min_clientes - existentes)
    if a_crear > 0:
        try:
            from faker import Faker
            fake = Faker(['es_AR'])
            for _ in range(a_crear):
                nombre = fake.first_name()[:50]
                apellido = fake.last_name()[:50]
                email = f"{nombre.lower()}.{apellido.lower()}.{random.randint(1000, 9999)}@{fake.domain_name()}"
                Cliente.objects.create(
                    nombre=nombre,
                    apellido=apellido,
                    telefono=f"+54 11 {random.randint(4000, 9999)}-{random.randint(1000, 9999)}",
                    email=email,
                    direccion=fake.street_address()[:200],
                )
            print(f"Clientes creados: {a_crear}")
        except Exception as e:
            print(f"No se pudieron generar clientes ficticios: {e}")


def random_date_in_last_days(days: int = 240) -> date:
    today = timezone.now().date()
    delta = random.randint(0, days)
    return today - timedelta(days=delta)


@transaction.atomic
def generar_pedidos(cantidad: int = 300):
    productos = list(Producto.objects.all())
    clientes = list(Cliente.objects.all())
    estados = list(EstadoPedido.objects.all())

    if not productos or not clientes or not estados:
        print("Faltan datos base (productos/clientes/estados) para generar pedidos.")
        return 0

    creados = 0
    for _ in range(cantidad):
        prod = random.choice(productos)
        cli = random.choice(clientes)
        estado = random.choices(
            estados,
            weights=[35, 25, 30, 10],  # más probabilidad de Pendiente/Completado
            k=1,
        )[0]
        fecha_pedido = random_date_in_last_days(240)
        fecha_entrega = fecha_pedido + timedelta(days=random.randint(1, 20))
        qty = random.randint(1, 100)

        # monto = precioUnitario * cantidad * factor
        precio = Decimal(prod.precioUnitario)
        factor = Decimal(str(random.uniform(0.9, 1.3)))
        monto = (precio * qty * factor).quantize(Decimal('0.01'))

        Pedido.objects.create(
            cliente=cli,
            producto=prod,
            fecha_pedido=fecha_pedido,
            fecha_entrega=fecha_entrega,
            cantidad=qty,
            especificaciones="Generado para pruebas de estadísticas",
            monto_total=monto,
            estado=estado,
        )
        creados += 1

    return creados


if __name__ == '__main__':
    try:
        ensure_estados()
        ensure_productos_y_clientes()
        n = generar_pedidos(300)
        print(f"Pedidos generados: {n}")
    except KeyboardInterrupt:
        print("\nOperación cancelada por el usuario")
    except Exception as e:
        import traceback
        print(f"\nError inesperado: {e}")
        traceback.print_exc()
