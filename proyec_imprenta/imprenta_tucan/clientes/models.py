from django.db import models


class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    razon_social = models.CharField(max_length=150, blank=True, null=True, db_column='razónSocial')
    direccion = models.CharField(max_length=200, db_column='dirección')
    # Ciudad y provincia dejan de tener choices embebidos para ser parametrizados vía configuracion.Parametro (JSON)
    ciudad = models.CharField(max_length=100, default='Posadas')
    provincia = models.CharField(max_length=100, default='Misiones')
    pais = models.CharField(max_length=100, default='Argentina')
    telefono = models.CharField(max_length=20)
    celular = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True)
    estado = models.CharField(max_length=10, choices=[('Activo', 'Activo'), ('Inactivo', 'Inactivo')], default='Activo', db_column='estadoCliente')
    # Ranking dinámico de clientes estratégicos
    puntaje_estrategico = models.FloatField(default=0)
    fecha_ultima_actualizacion = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.razon_social or 'Sin razón social'})"
