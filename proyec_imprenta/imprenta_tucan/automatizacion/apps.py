from django.apps import AppConfig


class AutomatizacionConfig(AppConfig):
    name = 'automatizacion'

    def ready(self):
        import automatizacion.signals  # noqa: F401 — registra signals al arrancar

        # T-01: AUTOMATION_WEBHOOK_SECRET es obligatorio.
        # Si no está configurado en el entorno, el sistema arranca pero los
        # webhooks aceptan cualquier request — riesgo de seguridad crítico.
        from django.conf import settings
        import warnings
        if not getattr(settings, "AUTOMATION_WEBHOOK_SECRET", ""):
            warnings.warn(
                "AUTOMATION_WEBHOOK_SECRET no está configurado. "
                "Los endpoints de webhook no tienen autenticación. "
                "Configurá esta variable de entorno antes de pasar a producción.",
                stacklevel=2,
            )