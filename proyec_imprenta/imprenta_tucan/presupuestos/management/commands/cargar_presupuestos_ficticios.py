from django.core.management.base import BaseCommand
from presupuestos.models import Presupuesto, PresupuestoDetalle
from productos.models import Producto
from clientes.models import Cliente
from faker import Faker
import random
from datetime import timedelta, date


class Command(BaseCommand):
    help = 'Carga 10 presupuestos ficticios con detalles'

    def handle(self, *args, **kwargs):
        fake = Faker('es_AR')
        productos = list(Producto.objects.all())
        clientes = list(Cliente.objects.all())
        if not productos or not clientes:
            self.stdout.write(self.style.ERROR('Debe haber productos y clientes cargados.'))
            return
        for i in range(10):
            cliente = random.choice(clientes)
            numero = f"P-{fake.unique.random_int(1000, 9999)}"
            validez = date.today() + timedelta(days=random.randint(5, 30))
            total = 0
            presupuesto = Presupuesto.objects.create(
                numero=numero,
                cliente=cliente,
                validez=validez,
                total=0,
                estado=random.choice(['Activo', 'Inactivo']),
                observaciones=fake.sentence()
            )
            detalles = []
            for _ in range(random.randint(1, 4)):
                producto = random.choice(productos)
                cantidad = random.randint(1, 10)
                precio_unitario = float(producto.precioUnitario)
                subtotal = cantidad * precio_unitario
                detalle = PresupuestoDetalle(
                    presupuesto=presupuesto,
                    producto=producto,
                    cantidad=cantidad,
                    precio_unitario=precio_unitario,
                    subtotal=subtotal
                )
                detalle.save()
                total += subtotal
                detalles.append(detalle)
            presupuesto.total = total
            presupuesto.save()
            self.stdout.write(self.style.SUCCESS(
                f'Presupuesto {presupuesto.numero} creado con {len(detalles)} productos.'))
