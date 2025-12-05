from django.core.management.base import BaseCommand
from insumos.models import Insumo
from proveedores.models import Proveedor
from pedidos.models import Pedido, EstadoPedido
from usuarios.models import Usuario
from productos.models import Producto
from clientes.models import Cliente
from django.utils import timezone

class Command(BaseCommand):
    help = 'Carga datos de ejemplo para insumos, proveedores y pedidos'

    def handle(self, *args, **options):
        proveedor, _ = Proveedor.objects.get_or_create(nombre='Proveedor Ejemplo', apellido='Ejemplo', cuit='20-12345678-9', email='proveedor@ejemplo.com', telefono='123456789', direccion='Calle Falsa 123', rubro='Papel', activo=True)
        insumo, _ = Insumo.objects.get_or_create(codigo='PAP001', defaults={
            'nombre': 'Papel Ilustración',
            'proveedor': proveedor,
            'cantidad': 1000,
            'precio_unitario': 10.5,
            'categoria': 'Papel',
            'stock': 1000,
            'precio': 10.5,
            'activo': True
        })
        estado, _ = EstadoPedido.objects.get_or_create(nombre='pendiente')
        producto, _ = Producto.objects.get_or_create(nombreProducto='Producto Ejemplo', precioUnitario=100, activo=True)
        cliente, _ = Cliente.objects.get_or_create(nombre='Cliente Ejemplo', apellido='Simulado', direccion='Calle Cliente 456', email='cliente@ejemplo.com', telefono='987654321')
        usuario, _ = Usuario.objects.get_or_create(email='admin@ejemplo.com', defaults={'nombre':'Admin','apellido':'Ejemplo','is_staff':True,'is_superuser':True})
        Pedido.objects.create(cliente=cliente, producto=producto, fecha_entrega=timezone.now().date(), cantidad=500, especificaciones='Pedido de prueba', monto_total=5000, estado=estado)
        # Generar datos simulados para ProyeccionInsumo
        from insumos.models import ProyeccionInsumo
        import random
        from datetime import timedelta
        periodo_actual = timezone.now().strftime('%Y-%m')
        insumos = Insumo.objects.all()
        proveedores = Proveedor.objects.all()
        for insumo in insumos:
            proveedor_sugerido = random.choice(list(proveedores)) if proveedores else None
            cantidad_proyectada = random.randint(100, 1000)
            ProyeccionInsumo.objects.update_or_create(
                insumo=insumo,
                periodo=periodo_actual,
                defaults={
                    'cantidad_proyectada': cantidad_proyectada,
                    'proveedor_sugerido': proveedor_sugerido,
                    'estado': 'pendiente',
                }
            )
        self.stdout.write(self.style.SUCCESS('Proyecciones de insumos simuladas cargadas correctamente.'))
        self.stdout.write(self.style.SUCCESS('Datos de ejemplo cargados correctamente.'))
