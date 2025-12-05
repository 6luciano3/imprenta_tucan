from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    name = 'auditoria'
    verbose_name = 'Auditoría'

    def ready(self):
        from . import signals  # noqa: F401
