from __future__ import annotations

from django.core.management.base import BaseCommand

from geo.models import Ciudad
from configuracion.models import Parametro, GrupoParametro

MISIONES_CIUDADES = [
    "Posadas", "Garupá", "Candelaria", "Apóstoles", "Azara", "San José", "Concepción de la Sierra",
    "Tres Capones", "Santa María", "Itacaruaré", "Leandro N. Alem", "Caá Yarí", "Gobernador López",
    "Oberá", "Guaraní", "Los Helechos", "Panambí", "Alba Posse", "San Javier", "Florentino Ameghino",
    "Aristóbulo del Valle", "Campo Grande", "2 de Mayo", "San Vicente", "El Soberbio", "San Pedro",
    "Bernardo de Irigoyen", "Puerto Esperanza", "Puerto Libertad", "Wanda", "Puerto Iguazú",
    "San Antonio", "Colonia Delicia", "Colonia Victoria", "Eldorado", "Montecarlo", "Caraguatay",
    "Puerto Piray", "Jardín América", "Hipólito Yrigoyen", "Ruiz de Montoya",
    "Capioví", "Puerto Rico", "Garuhapé", "El Alcázar", "Campo Viera", "Campo Ramón", "Santa Ana",
    "Profundidad", "Mártires", "Corpus", "General Urquiza", "Bonpland", "Santo Pipó", "San Ignacio",
    "Loreto", "Santiago de Liniers", "Pozo Azul"
]


class Command(BaseCommand):
    help = "Carga ciudades de la Provincia de Misiones y actualiza el parámetro de clientes"

    def handle(self, *args, **options):
        creadas = 0
        for nombre in MISIONES_CIUDADES:
            obj, created = Ciudad.objects.get_or_create(
                nombre=nombre, defaults={"provincia": "Misiones", "activo": True}
            )
            if created:
                creadas += 1

        # Actualizar parámetro CLIENTES_CIUDADES para fallback/select por nombre
        grp, _ = GrupoParametro.objects.get_or_create(
            codigo="CLIENTES", defaults={"nombre": "Clientes"}
        )
        Parametro.set(
            "CLIENTES_CIUDADES", MISIONES_CIUDADES, tipo=Parametro.TIPO_JSON, grupo=grp, nombre="Ciudades disponibles"
        )
        Parametro.set(
            "CLIENTES_CIUDAD_DEFAULT", "Posadas", tipo=Parametro.TIPO_CADENA, grupo=grp, nombre="Ciudad por defecto"
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Ciudades de Misiones cargadas. Nuevas: {creadas}. Total: {Ciudad.objects.filter(provincia='Misiones').count()}"
            )
        )
