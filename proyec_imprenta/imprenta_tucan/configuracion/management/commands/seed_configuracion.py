from __future__ import annotations

from django.core.management.base import BaseCommand

from configuracion.models import GrupoParametro, Parametro


class Command(BaseCommand):
    help = "Siembra grupos y parámetros base para clientes (ciudades). Ejecutar una sola vez o idempotente."

    def handle(self, *args, **options):
        grp_clientes, _ = GrupoParametro.objects.get_or_create(
            codigo="CLIENTES",
            defaults={"nombre": "Clientes", "descripcion": "Parámetros relacionados a la gestión de clientes"},
        )

        ciudades_default = ["Posadas", "Eldorado", "Oberá"]
        Parametro.set(
            "CLIENTES_CIUDADES",
            ciudades_default,
            tipo=Parametro.TIPO_JSON,
            grupo=grp_clientes,
            nombre="Listado de ciudades permitidas",
            descripcion="Lista desplegable en formulario de clientes",
        )
        Parametro.set(
            "CLIENTES_CIUDAD_DEFAULT",
            "Posadas",
            tipo=Parametro.TIPO_CADENA,
            grupo=grp_clientes,
            nombre="Ciudad por defecto",
            descripcion="Valor preseleccionado si no se indica otro",
        )

        self.stdout.write(self.style.SUCCESS("Seed de configuración de ciudades de clientes aplicada."))
