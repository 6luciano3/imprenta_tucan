from django.apps import AppConfig


class AutomatizacionConfig(AppConfig):
    name = 'automatizacion'

    def ready(self):
        import automatizacion.signals  # noqa: F401 — registra signals al arrancar

