from django.core.management.base import BaseCommand
from roles.models import Rol
from permisos.models import Permiso

PROFILES = {
    'Atención al Público': {
        'descripcion': 'Personal encargado de la atención al público y gestión de pedidos',
        'modules': ['Pedidos', 'Insumos'],
    },
    'Personal de Administración': {
        'descripcion': 'Personal administrativo encargado de gestionar usuarios, clientes, proveedores, productos y reportes',
        'modules': ['Usuarios', 'Clientes', 'Proveedores', 'Productos', 'Reportes'],
    },
}


class Command(BaseCommand):
    help = "Crea o actualiza roles predefinidos asociando permisos por módulos. Por defecto: 'Atención al Público'."

    def add_arguments(self, parser):
        parser.add_argument(
            '--role', type=str, help="Nombre del rol a crear/actualizar. Opciones: 'Atención al Público', 'Personal de Administración'.")
        parser.add_argument('--all', action='store_true', help='Crear/actualizar todos los roles predefinidos.')
        parser.add_argument('--force', action='store_true',
                            help='Forzar actualización de descripción y permisos aunque el rol exista.')
        parser.add_argument('--dry-run', action='store_true', help='Mostrar acciones sin realizar cambios.')

    def _upsert_role(self, nombre_rol: str, descripcion: str, modules: list, *, force: bool, dry: bool):
        permisos_qs = Permiso.objects.filter(modulo__in=modules, estado='Activo').order_by('modulo', 'nombre')
        if not permisos_qs.exists():
            self.stdout.write(self.style.WARNING(
                f'No se encontraron permisos activos para módulos: {", ".join(modules)}.'))

        rol, created = Rol.objects.get_or_create(nombreRol=nombre_rol, defaults={
                                                 'descripcion': descripcion, 'estado': 'Activo'})

        if created:
            self.stdout.write(self.style.SUCCESS(f"Rol creado: {nombre_rol}"))
        else:
            self.stdout.write(self.style.WARNING(f"Rol ya existía: {nombre_rol}"))

        if dry:
            self.stdout.write(self.style.WARNING(
                f"[dry-run] Se asociarían {permisos_qs.count()} permisos al rol {nombre_rol}."))
            return

        if created or force:
            rol.descripcion = descripcion
            rol.save()
            rol.permisos.set(permisos_qs)
            self.stdout.write(self.style.SUCCESS(
                f"Permisos asociados a '{nombre_rol}' ({permisos_qs.count()}): {[p.nombre for p in permisos_qs]}"))
        else:
            actuales_ids = set(rol.permisos.values_list('id', flat=True))
            nuevos = [p for p in permisos_qs if p.id not in actuales_ids]
            if nuevos:
                for p in nuevos:
                    rol.permisos.add(p)
                self.stdout.write(self.style.SUCCESS(
                    f"Se añadieron {len(nuevos)} permisos faltantes a '{nombre_rol}'."))
            else:
                if hasattr(self.style, 'NOTICE'):
                    self.stdout.write(self.style.NOTICE(f"'{nombre_rol}': sin cambios en permisos."))
                else:
                    self.stdout.write('Sin cambios en permisos.')

    def handle(self, *args, **options):
        role = options.get('role')
        create_all = options.get('all')
        force = options.get('force')
        dry = options.get('dry_run')

        roles_to_process = []
        if create_all:
            roles_to_process = list(PROFILES.keys())
        elif role:
            if role not in PROFILES:
                self.stdout.write(self.style.ERROR(f"Rol no soportado: {role}. Opciones: {', '.join(PROFILES.keys())}"))
                return
            roles_to_process = [role]
        else:
            # Default
            roles_to_process = ['Atención al Público']

        for nombre in roles_to_process:
            profile = PROFILES[nombre]
            self._upsert_role(nombre, profile['descripcion'], profile['modules'], force=force, dry=dry)

        self.stdout.write(self.style.SUCCESS('Proceso finalizado.'))
