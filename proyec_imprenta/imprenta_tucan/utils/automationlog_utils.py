from .core_models import AutomationLog
from django.contrib.auth import get_user_model


def registrar_automation_log(evento, descripcion, usuario=None, datos=None):
    log = AutomationLog.objects.create(
        evento=evento,
        descripcion=descripcion,
        usuario=usuario,
        datos=datos or {}
    )
    return log
