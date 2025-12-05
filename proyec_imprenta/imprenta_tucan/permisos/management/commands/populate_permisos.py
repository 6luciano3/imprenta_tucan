from django.core.management.base import BaseCommand
from permisos.models import Permiso

SAMPLE_PERMISOS = [
    {
        "nombre": "Gestion Usuarios",
        "descripcion": "Permite crear, listar y editar usuarios del sistema",
        "modulo": "Usuarios",
        "acciones": ["Crear", "Listar", "Editar", "Desactivar", "Reactivar"],
    },
    {
        "nombre": "Gestion Productos",
        "descripcion": "Administración completa de productos: altas, modificaciones, bajas lógicas",
        "modulo": "Productos",
        "acciones": ["Crear", "Listar", "Editar", "Eliminar", "Exportar"],
    },
    {
        "nombre": "Gestion Pedidos",
        "descripcion": "Permisos sobre el ciclo de vida del pedido (crear, aprobar, rechazar, cerrar)",
        "modulo": "Pedidos",
        "acciones": ["Crear", "Listar", "Aprobar", "Rechazar", "Cerrar"],
    },
    {
        "nombre": "Reportes Ventas",
        "descripcion": "Acceso a reportes y estadísticas de ventas y facturación mensual",
        "modulo": "Reportes",
        "acciones": ["Ver", "Exportar", "Imprimir"],
    },
    {
        "nombre": "Gestion Insumos",
        "descripcion": "Gestión de insumos y existencias en stock (altas, ajustes y bajas)",
        "modulo": "Insumos",
        "acciones": ["Crear", "Listar", "Editar", "Actualizar", "Eliminar"],
    },
    {
        "nombre": "Gestión de Clientes",
        "descripcion": "Administración de clientes: altas, modificaciones y bajas",
        "modulo": "Clientes",
        "acciones": ["Crear", "Listar", "Editar", "Eliminar"],
    },
    {
        "nombre": "Gestionar Proveedores",
        "descripcion": "Administración de proveedores: altas, modificaciones y bajas",
        "modulo": "Proveedores",
        "acciones": ["Crear", "Listar", "Editar", "Eliminar"],
    },
]


class Command(BaseCommand):
    help = "Puebla la tabla de Permiso con registros de ejemplo si está vacía o agrega los que falten."

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Crear también si ya existen (solo los que falten por nombre).')
        parser.add_argument('--dry-run', action='store_true', help='Mostrar lo que se haría sin escribir cambios.')

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        for data in SAMPLE_PERMISOS:
            if not options['force'] and Permiso.objects.filter(nombre__iexact=data['nombre']).exists():
                skipped += 1
                continue
            if options.get('dry_run'):
                self.stdout.write(self.style.WARNING(f"[dry-run] Crearía permiso: {data['nombre']}"))
                continue
            permiso, was_created = Permiso.objects.get_or_create(
                nombre=data['nombre'],
                defaults={
                    'descripcion': data['descripcion'],
                    'modulo': data['modulo'],
                    'acciones': data['acciones'],
                    'estado': 'Activo'
                }
            )
            if was_created:
                created += 1
            else:
                # Si existe pero se pidió force y no es dry-run, actualizar acciones y descripción
                if options['force']:
                    permiso.descripcion = data['descripcion']
                    permiso.modulo = data['modulo']
                    permiso.acciones = data['acciones']
                    permiso.save()
                    self.stdout.write(self.style.SUCCESS(f"Actualizado permiso existente: {permiso.nombre}"))
                skipped += 1
        self.stdout.write(self.style.SUCCESS(f"Permisos creados: {created}"))
        if hasattr(self.style, 'NOTICE'):
            self.stdout.write(self.style.NOTICE(f"Permisos omitidos: {skipped}"))
        else:
            self.stdout.write(self.style.WARNING(f"Permisos omitidos: {skipped}"))
        if options.get('dry_run'):
            self.stdout.write(self.style.WARNING("Ejecute nuevamente sin --dry-run para aplicar cambios."))
