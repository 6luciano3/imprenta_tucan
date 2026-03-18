from django.db import models


class EstadoCompra(models.Model):
    nombre = models.CharField(max_length=30, unique=True)

    class Meta:
        verbose_name = "Estado de Compra"
        verbose_name_plural = "Estados de Compra"

    def __str__(self):
        return self.nombre


class OrdenCompra(models.Model):
    proveedor = models.ForeignKey(
        "proveedores.Proveedor", on_delete=models.CASCADE, related_name="ordenes_compra_app"
    )
    estado = models.ForeignKey(
        EstadoCompra, on_delete=models.PROTECT, related_name="ordenes"
    )
    fecha_creacion = models.DateField(auto_now_add=True)
    fecha_recepcion = models.DateField(null=True, blank=True)
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    observaciones = models.TextField(blank=True)
    usuario = models.ForeignKey(
        "usuarios.Usuario", on_delete=models.SET_NULL, null=True, blank=True, related_name="ordenes_compra"
    )
    solicitud_cotizacion = models.ForeignKey(
        "automatizacion.SolicitudCotizacion",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ordenes_compra",
        help_text="Solicitud de cotizacion confirmada que origino esta orden"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Orden de Compra"
        verbose_name_plural = "Ordenes de Compra"

    def __str__(self):
        return f"OC-{self.pk:04d} | {self.proveedor} | {self.estado}"

    def calcular_total(self):
        total = sum(d.subtotal() for d in self.detalles.all())
        self.monto_total = total
        self.save(update_fields=["monto_total"])
        return total


class DetalleOrdenCompra(models.Model):
    orden = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name="detalles")
    insumo = models.ForeignKey(
        "insumos.Insumo", on_delete=models.CASCADE, related_name="detalles_orden_compra"
    )
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f"{self.insumo.nombre} x {self.cantidad} @ ${self.precio_unitario}"


class Remito(models.Model):
    orden_compra = models.ForeignKey(
        OrdenCompra, on_delete=models.SET_NULL, null=True, blank=True, related_name="remitos"
    )
    proveedor = models.ForeignKey(
        "proveedores.Proveedor", on_delete=models.CASCADE, related_name="remitos_compras"
    )
    numero = models.CharField(max_length=50)
    fecha = models.DateField()
    usuario = models.ForeignKey(
        "usuarios.Usuario", on_delete=models.SET_NULL, null=True, blank=True, related_name="remitos_compras"
    )
    observaciones = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Remito"
        verbose_name_plural = "Remitos"

    def __str__(self):
        return f"Remito {self.numero} - {self.proveedor} ({self.fecha})"


class DetalleRemito(models.Model):
    remito = models.ForeignKey(Remito, on_delete=models.CASCADE, related_name="detalles")
    insumo = models.ForeignKey(
        "insumos.Insumo", on_delete=models.CASCADE, related_name="detalles_remito_compras"
    )
    cantidad = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.insumo.nombre} x {self.cantidad}"
