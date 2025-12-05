from django.db import models
from permisos.models import Permiso


class Rol(models.Model):
    idRol = models.AutoField(primary_key=True)
    nombreRol = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=10, choices=[('Activo', 'Activo'), ('Inactivo', 'Inactivo')], default='Activo')
    permisos = models.ManyToManyField(Permiso, related_name='roles', blank=True)

    def __str__(self):
        return self.nombreRol

    class Meta:
        db_table = 'rol'
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'
