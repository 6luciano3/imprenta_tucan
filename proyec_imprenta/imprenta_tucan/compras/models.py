from django.db import models


class EstadoCompra(models.Model):
    nombre = models.CharField(max_length=30, unique=True)

    class Meta:
        verbose_name = "Estado de Compra"
        verbose_name_plural = "Estados de Compra"

    def __str__(self):
        return self.nombre


class OrdenCompra(models.Model):
    CONDICIONES_PAGO = [
        ('contado', 'Contado'),
        ('15_dias', '15 días'),
        ('30_dias', '30 días'),
        ('60_dias', '60 días'),
        ('90_dias', '90 días'),
    ]
    
    proveedor = models.ForeignKey(
        "proveedores.Proveedor", on_delete=models.CASCADE, related_name="ordenes_compra_app"
    )
    estado = models.ForeignKey(
        EstadoCompra, on_delete=models.PROTECT, related_name="ordenes"
    )
    fecha_creacion = models.DateField(auto_now_add=True)
    fecha_recepcion = models.DateField(null=True, blank=True)
    fecha_entrega = models.DateField(null=True, blank=True, help_text="Fecha estimada de entrega")
    condicion_pago = models.CharField(max_length=20, choices=CONDICIONES_PAGO, default='contado')
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


class MovimientoStock(models.Model):
    TIPOS = [
        ("entrada", "Entrada"),
        ("salida", "Salida"),
        ("ajuste_positivo", "Ajuste positivo"),
        ("ajuste_negativo", "Ajuste negativo"),
    ]
    ORIGENES = [
        ("remito", "Remito de compra"),
        ("produccion", "Orden de produccion"),
        ("ajuste", "Ajuste manual"),
        ("automatico", "Sistema automatico"),
    ]
    insumo = models.ForeignKey(
        "insumos.Insumo", on_delete=models.CASCADE, related_name="movimientos_stock"
    )
    tipo = models.CharField(max_length=20, choices=TIPOS)
    origen = models.CharField(max_length=20, choices=ORIGENES)
    cantidad = models.PositiveIntegerField()
    stock_anterior = models.IntegerField(default=0)
    stock_posterior = models.IntegerField(default=0)
    referencia = models.CharField(max_length=100, blank=True, help_text="Ej: Remito R-0001, OC-0002")
    observaciones = models.TextField(blank=True)
    usuario = models.ForeignKey(
        "usuarios.Usuario", on_delete=models.SET_NULL, null=True, blank=True, related_name="movimientos_stock"
    )
    remito = models.ForeignKey(
        Remito, on_delete=models.SET_NULL, null=True, blank=True, related_name="movimientos"
    )
    fecha = models.DateField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Movimiento de Stock"
        verbose_name_plural = "Movimientos de Stock"

    def __str__(self):
        return f"{self.get_tipo_display()} | {self.insumo.nombre} | {self.cantidad} | {self.fecha}"
