import uuid
from django.db import models
from clientes.models import Cliente


class Presupuesto(models.Model):
    RESPUESTA_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aceptado', 'Aceptado'),
        ('rechazado', 'Rechazado'),
    ]

    numero = models.CharField(max_length=20, unique=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='presupuestos')
    razon_social = models.CharField(max_length=150, blank=True, null=True,
                                    help_text="Razón social vinculada al presupuesto")
    fecha = models.DateField(auto_now_add=True)
    validez = models.DateField(blank=True, null=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=10, choices=[('Activo', 'Activo'), ('Inactivo', 'Inactivo')], default='Activo')
    observaciones = models.TextField(blank=True, null=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    respuesta_cliente = models.CharField(
        max_length=10,
        choices=RESPUESTA_CHOICES,
        default='pendiente',
        verbose_name='Respuesta del cliente',
    )
    pedido_relacionado = models.ForeignKey(
        'pedidos.Pedido',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='presupuestos_origen',
        verbose_name='Pedido generado',
    )
    recordatorio_enviado_fecha = models.DateField(
        null=True, blank=True,
        verbose_name='Fecha último recordatorio enviado',
        help_text='Se actualiza cada vez que se envía un recordatorio automático. Evita duplicados en el mismo día.',
    )


class PresupuestoDetalle(models.Model):
    presupuesto = models.ForeignKey(Presupuesto, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    descuento = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Descuento en %")
    iva = models.DecimalField(max_digits=5, decimal_places=2, default=21, help_text="IVA en %")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        from decimal import Decimal
        neto = self.cantidad * self.precio_unitario
        con_descuento = neto * (1 - self.descuento / Decimal('100'))
        self.subtotal = con_descuento * (1 + self.iva / Decimal('100'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.producto} x {self.cantidad}"

    class Meta:
        ordering = ['-id']
