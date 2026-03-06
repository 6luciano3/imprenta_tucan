from django.apps import AppConfig


class InsumosConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'insumos'

    def ready(self):
        import insumos.signals  # noqa: F401 — registra los signals al levantar la app
