from django.db import models


class Rubro(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Proveedor(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100, default='Ejemplo')
    cuit = models.CharField(max_length=13, unique=True)  # Formato: XX-XXXXXXXX-X
    email = models.EmailField()
    telefono = models.CharField(max_length=20)
    direccion = models.TextField()
    rubro = models.CharField(max_length=50)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        # Mostrar nombre y CUIT si está disponible
        return f"{self.nombre}{f' ({self.cuit})' if self.cuit else ''}"


# Modelo para parametrización de proveedores
class ProveedorParametro(models.Model):
    clave = models.CharField(max_length=50, unique=True)
    valor = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.clave}: {self.valor}"
