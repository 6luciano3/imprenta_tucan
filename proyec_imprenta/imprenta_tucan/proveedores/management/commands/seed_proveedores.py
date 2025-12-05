from django.core.management.base import BaseCommand
from django.db import transaction, connection
from django.utils import timezone
from proveedores.models import Proveedor

import random
from faker import Faker


class Command(BaseCommand):
    help = "Crea proveedores de prueba para la industria gráfica"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=30,
            help="Cantidad de proveedores a crear (por defecto: 30)",
        )

    def handle(self, *args, **options):
        count = max(1, options.get("count") or 30)

        fake = Faker(["es_AR", "es_ES", "es_MX"])  # direcciones y teléfonos en español
        rubros = [
            "Papelería",
            "Tintas y Químicos",
            "Maquinaria de Impresión",
            "Repuestos y Mantenimiento",
            "Planchas Offset",
            "Serigrafía",
            "Sublimación",
            "Flexografía",
            "Corte y Troquelado",
            "Vinilos y Adhesivos",
            "Cartón y Packaging",
            "Plotters y Gran Formato",
        ]

        prefijos_cuit = ["20", "23", "27", "30", "33"]

        def generar_cuit_unico(existentes: set) -> str:
            # Formato: XX-XXXXXXXX-X
            for _ in range(5000):
                pref = random.choice(prefijos_cuit)
                cuerpo = f"{random.randint(10_000_000, 99_999_999)}"
                ver = str(random.randint(0, 9))
                cuit = f"{pref}-{cuerpo}-{ver}"
                if cuit not in existentes:
                    existentes.add(cuit)
                    return cuit
            # Fallback improbable
            return f"30-{random.randint(10_000_000, 99_999_999)}-0"

        def nombre_proveedor():
            bases = [
                "Gráfica", "Impresiones", "Offset", "Flexo", "Serigrafía",
                "Plotter", "Diseño", "Tintas", "Papelera", "Packaging",
            ]
            sufijos = [
                "Norte", "Sur", "Este", "Oeste", "Centro",
                "Express", "Plus", "Premium", "Pro", "Industrial",
            ]
            ciudad = fake.city()
            return f"{random.choice(bases)} {random.choice(sufijos)} {ciudad}"[:100]

        creados = 0
        existentes = set(Proveedor.objects.values_list("cuit", flat=True))

        with transaction.atomic():
            for i in range(count):
                nombre = nombre_proveedor()
                cuit = generar_cuit_unico(existentes)
                email = fake.unique.company_email()
                telefono = fake.phone_number()
                direccion = fake.address().replace("\n", ", ")
                rubro = random.choice(rubros)
                activo = 1 if (random.random() > 0.15) else 0  # ~85% activos
                fecha = timezone.now()

                # Insertar vía SQL para satisfacer columnas legadas NOT NULL (apellido, empresa, fecha_creacion)
                sql = (
                    "INSERT INTO proveedores_proveedor "
                    "(nombre, cuit, email, telefono, direccion, rubro, fecha_creacion, activo, apellido, empresa) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                )
                params = [
                    nombre,
                    cuit,
                    email,
                    telefono,
                    direccion,
                    rubro,
                    fecha.strftime("%Y-%m-%d %H:%M:%S"),
                    activo,
                    "",
                    "",
                ]
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(sql, params)
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Fallo al insertar: {e!r}"))
                    self.stderr.write(self.style.ERROR(f"SQL: {sql}"))
                    self.stderr.write(self.style.ERROR(f"Params: {params}"))
                    raise
                creados += 1

        self.stdout.write(self.style.SUCCESS(f"Se crearon {creados} proveedores de prueba."))
