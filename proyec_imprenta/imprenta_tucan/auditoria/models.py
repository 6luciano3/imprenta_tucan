from django.conf import settings
from django.db import models


class AuditEntry(models.Model):
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_CHOICES = (
        (ACTION_CREATE, 'Crear'),
        (ACTION_UPDATE, 'Actualizar'),
        (ACTION_DELETE, 'Eliminar'),
    )

    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='audit_entries'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    path = models.CharField(max_length=512, blank=True)
    method = models.CharField(max_length=10, blank=True)

    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    object_id = models.CharField(max_length=64)
    object_repr = models.TextField(blank=True)

    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    # TextField para compatibilidad amplia con SQLite (evita dependencia de JSON1 en tests)
    changes = models.TextField(null=True, blank=True)
    extra = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['app_label', 'model']),
            models.Index(fields=['object_id']),
            models.Index(fields=['action']),
            models.Index(fields=['timestamp'])
        ]

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] {self.action.upper()} {self.app_label}.{self.model}({self.object_id})"
