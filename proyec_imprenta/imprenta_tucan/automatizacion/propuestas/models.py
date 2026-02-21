from django.db import models
from clientes.models import Cliente
from productos.models import Producto

class ComboOferta(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='combos_oferta')
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    productos = models.ManyToManyField(Producto, through='ComboOfertaProducto')
    descuento = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # %
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    enviada = models.BooleanField(default=False)
    aceptada = models.BooleanField(default=False)
    rechazada = models.BooleanField(default=False)
    fecha_envio = models.DateTimeField(null=True, blank=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Combo {self.nombre} para {self.cliente}"  

class ComboOfertaProducto(models.Model):
    combo = models.ForeignKey(ComboOferta, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.producto} x{self.cantidad} (Combo {self.combo.nombre})"
