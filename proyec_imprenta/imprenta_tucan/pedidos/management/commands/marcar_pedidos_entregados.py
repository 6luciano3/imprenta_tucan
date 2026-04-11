"""
Management command: marcar_pedidos_entregados

Marca como "Entregado" todos los pedidos cuya fecha_entrega ya pasó
y que no estén ya en estados terminales (Entregado / Cancelado).

Uso:
    python manage.py marcar_pedidos_entregados
    python manage.py marcar_pedidos_entregados --dry-run
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from pedidos.models import Pedido, EstadoPedido


ESTADOS_TERMINALES = ('entregado', 'cancelado')


class Command(BaseCommand):
    help = 'Marca como Entregado los pedidos con fecha_entrega vencida'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué pedidos se actualizarían sin modificar la BD',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        hoy = timezone.localdate()

        estado_entregado = EstadoPedido.objects.filter(nombre__icontains='entregado').first()
        if not estado_entregado:
            estado_entregado = EstadoPedido.objects.create(nombre='Entregado')
            self.stdout.write(self.style.WARNING('Se creó el estado "Entregado" en la BD.'))

        # Pedidos vencidos que NO están en estados terminales
        qs = Pedido.objects.filter(fecha_entrega__lt=hoy)
        for termino in ESTADOS_TERMINALES:
            qs = qs.exclude(estado__nombre__icontains=termino)

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No hay pedidos vencidos pendientes de actualizar.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(f'[DRY-RUN] Se actualizarían {total} pedido(s):'))
            for p in qs.select_related('cliente', 'estado').order_by('fecha_entrega'):
                self.stdout.write(f'  - Pedido #{p.id} | {p.cliente} | Entrega: {p.fecha_entrega} | Estado actual: {p.estado}')
            return

        # Llamar .save() individualmente para que Pedido.save() dispare
        # las señales de notificación de entrega al cliente.
        actualizados = 0
        errores = 0
        for pedido in qs.select_related('estado').order_by('fecha_entrega'):
            try:
                pedido.estado = estado_entregado
                pedido.save()
                actualizados += 1
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(f'  Error en Pedido #{pedido.id}: {exc}')
                )
                errores += 1

        self.stdout.write(self.style.SUCCESS(
            f'{actualizados} pedido(s) marcados como "{estado_entregado.nombre}".'
            + (f' ({errores} errores — revisar logs)' if errores else '')
        ))
