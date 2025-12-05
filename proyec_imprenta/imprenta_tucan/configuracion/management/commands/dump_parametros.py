from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from ...models import Parametro, FeatureFlag, ListaConfig, GrupoParametro


class Command(BaseCommand):
    help = "Exporta parámetros, feature flags y listas a JSON legible"

    def add_arguments(self, parser):  # pragma: no cover - interfaz CLI
        parser.add_argument("--indent", type=int, default=2, help="Indentación del JSON")

    def handle(self, *args, **options):
        indent = options["indent"]

        grupos = list(
            GrupoParametro.objects.all().values("codigo", "nombre", "descripcion")
        )
        params = list(
            Parametro.objects.all().values(
                "codigo",
                "grupo__codigo",
                "nombre",
                "descripcion",
                "tipo",
                "valor",
                "activo",
                "editable",
            )
        )
        flags = list(
            FeatureFlag.objects.all().values("codigo", "descripcion", "activo")
        )
        listas = list(
            ListaConfig.objects.all().values(
                "codigo",
                "descripcion",
                "page_size",
                "max_page_size",
                "orden_default",
                "columnas_visibles",
                "activo",
            )
        )

        salida = {
            "grupos": grupos,
            "parametros": params,
            "feature_flags": flags,
            "listas": listas,
        }

        self.stdout.write(json.dumps(salida, ensure_ascii=False, indent=indent))
