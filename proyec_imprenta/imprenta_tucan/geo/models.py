from django.db import models


class Ciudad(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    provincia = models.CharField(max_length=120, blank=True)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ciudad"
        verbose_name_plural = "Ciudades"
        ordering = ["nombre"]

    def __str__(self):  # pragma: no cover
        return self.nombre
