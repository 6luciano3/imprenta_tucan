from django.core.management.base import BaseCommand
from configuracion.models import UnidadDeMedida


class Command(BaseCommand):
    help = 'Agrega unidades de medida de ejemplo al sistema'

    def handle(self, *args, **options):
        unidades = [
            {"nombre": "Metro", "simbolo": "m", "descripcion": "Unidad de longitud", "activo": True},
            {"nombre": "Kilogramo", "simbolo": "kg", "descripcion": "Unidad de masa", "activo": True},
            {"nombre": "Litro", "simbolo": "L", "descripcion": "Unidad de volumen", "activo": True},
            {"nombre": "Unidad", "simbolo": "u", "descripcion": "Unidad básica", "activo": True},
            {"nombre": "Centímetro", "simbolo": "cm", "descripcion": "Submúltiplo de metro", "activo": True},
        ]
        for data in unidades:
            obj, created = UnidadDeMedida.objects.get_or_create(
                nombre=data["nombre"],
                defaults={
                    "simbolo": data["simbolo"],
                    "descripcion": data["descripcion"],
                    "activo": data["activo"],
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Unidad creada: {obj.nombre}"))
            else:
                self.stdout.write(self.style.WARNING(f"Ya existe: {obj.nombre}"))
