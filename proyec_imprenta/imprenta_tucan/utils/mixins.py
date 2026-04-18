from django.db import models
from django.utils import timezone


class SoftDeleteMixin(models.Model):
    """
    Mixin de baja lógica estándar para todos los modelos del proyecto.

    Uso:
        class MiModelo(SoftDeleteMixin, models.Model):
            ...

    Provee:
        - activo: bool — False indica baja lógica
        - deleted_at: datetime — timestamp de la baja
        - delete(): marca como inactivo en lugar de borrar
        - restore(): reactiva el registro
        - objects_activos: manager que filtra solo activos
    """

    activo = models.BooleanField(default=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.activo = False
        self.deleted_at = timezone.now()
        self.save(update_fields=['activo', 'deleted_at'])

    def restore(self):
        self.activo = True
        self.deleted_at = None
        self.save(update_fields=['activo', 'deleted_at'])

    def hard_delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(activo=True)
