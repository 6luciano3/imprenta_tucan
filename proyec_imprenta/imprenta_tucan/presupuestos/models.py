from django.db import models
from clientes.models import Cliente


class Presupuesto(models.Model):
    numero = models.CharField(max_length=20, unique=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='presupuestos')
    razon_social = models.CharField(max_length=150, blank=True, null=True,
                                    help_text="Razón social vinculada al presupuesto")
    fecha = models.DateField(auto_now_add=True)
    validez = models.DateField(blank=True, null=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=10, choices=[('Activo', 'Activo'), ('Inactivo', 'Inactivo')], default='Activo')
    observaciones = models.TextField(blank=True, null=True)


class PresupuestoDetalle(models.Model):
    presupuesto = models.ForeignKey(Presupuesto, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.producto} x {self.cantidad}"

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"Presupuesto {self.presupuesto.numero} - {self.presupuesto.cliente}"
