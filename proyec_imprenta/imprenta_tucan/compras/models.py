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
        "proveedores.Proveedor", on_delete=models.PROTECT, related_name="ordenes_compra_app"
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
    enviada = models.BooleanField(default=False, help_text="Indica si la orden fue enviada al proveedor")
    fecha_envio = models.DateTimeField(null=True, blank=True, help_text="Fecha en que se envió la orden al proveedor")
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
        "insumos.Insumo", on_delete=models.PROTECT, related_name="detalles_orden_compra"
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
        "proveedores.Proveedor", on_delete=models.PROTECT, related_name="remitos_compras"
    )
    numero = models.CharField(max_length=50, unique=True)
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
        "insumos.Insumo", on_delete=models.PROTECT, related_name="detalles_remito_compras"
    )
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Precio al que se recibió el insumo en este remito"
    )

    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f"{self.insumo.nombre} x {self.cantidad} @ ${self.precio_unitario}"


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


class HistorialPrecioInsumo(models.Model):
    """Registro inmutable de cada cambio de precio de un insumo."""
    ORIGENES = [
        ('manual', 'Actualización manual'),
        ('ajuste_masivo', 'Ajuste masivo'),
        ('remito', 'Recepción de remito'),
        ('sc', 'Solicitud de cotización'),
    ]

    insumo = models.ForeignKey(
        'insumos.Insumo', on_delete=models.CASCADE, related_name='historial_precios'
    )
    precio_anterior = models.DecimalField(max_digits=10, decimal_places=2)
    precio_nuevo = models.DecimalField(max_digits=10, decimal_places=2)
    variacion_pct = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Variación porcentual respecto al precio anterior'
    )
    origen = models.CharField(max_length=20, choices=ORIGENES, default='manual')
    motivo = models.CharField(max_length=300, blank=True)
    usuario = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True
    )
    remito = models.ForeignKey(
        'compras.Remito', on_delete=models.SET_NULL, null=True, blank=True,
        help_text='Remito origen del cambio (si aplica)'
    )
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Historial de Precio'
        verbose_name_plural = 'Historial de Precios'

    def __str__(self):
        return f"{self.insumo.nombre} | ${self.precio_anterior} → ${self.precio_nuevo} | {self.fecha:%d/%m/%Y}"

    def save(self, *args, **kwargs):
        if self.precio_anterior and self.precio_anterior != 0:
            from decimal import Decimal
            self.variacion_pct = (
                (self.precio_nuevo - self.precio_anterior) / self.precio_anterior * 100
            ).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────
# ÓRDENES DE PAGO
# ─────────────────────────────────────────────

class OrdenPago(models.Model):
    ESTADOS = [
        ('pendiente',  'Pendiente'),
        ('aprobada',   'Aprobada'),
        ('pagada',     'Pagada'),
        ('anulada',    'Anulada'),
    ]
    MONEDAS = [
        ('ARS', 'Pesos argentinos (ARS)'),
        ('USD', 'Dólares (USD)'),
    ]

    numero = models.CharField(max_length=20, unique=True, editable=False)
    proveedor = models.ForeignKey(
        'proveedores.Proveedor', on_delete=models.PROTECT, related_name='ordenes_pago'
    )
    orden_compra = models.ForeignKey(
        OrdenCompra, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordenes_pago', help_text='Orden de compra asociada (opcional)'
    )
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    moneda = models.CharField(max_length=3, choices=MONEDAS, default='ARS')
    monto_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monto_retenciones = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monto_neto = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    fecha_pago = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True)
    usuario = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordenes_pago_creadas'
    )
    usuario_aprobacion = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordenes_pago_aprobadas'
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Orden de Pago'
        verbose_name_plural = 'Órdenes de Pago'

    def __str__(self):
        return f"OP-{self.numero} | {self.proveedor} | {self.get_estado_display()}"

    def save(self, *args, **kwargs):
        if not self.numero:
            ultimo = OrdenPago.objects.order_by('-id').first()
            siguiente = (ultimo.id + 1) if ultimo else 1
            self.numero = f'{siguiente:05d}'
        self.monto_neto = self.monto_total - self.monto_retenciones
        super().save(*args, **kwargs)

    def recalcular_totales(self):
        self.monto_total = sum(c.importe for c in self.comprobantes.all())
        self.monto_retenciones = sum(r.importe for r in self.retenciones.all())
        self.monto_neto = self.monto_total - self.monto_retenciones
        self.save(update_fields=['monto_total', 'monto_retenciones', 'monto_neto'])


class ComprobanteOrdenPago(models.Model):
    TIPOS = [
        ('factura_a', 'Factura A'),
        ('factura_b', 'Factura B'),
        ('factura_c', 'Factura C'),
        ('nota_credito', 'Nota de Crédito'),
        ('nota_debito', 'Nota de Débito'),
        ('recibo', 'Recibo'),
    ]
    orden_pago = models.ForeignKey(OrdenPago, on_delete=models.CASCADE, related_name='comprobantes')
    tipo = models.CharField(max_length=20, choices=TIPOS, default='factura_a')
    numero = models.CharField(max_length=50, help_text='Ej: 0001-00012345')
    fecha = models.DateField()
    importe = models.DecimalField(max_digits=14, decimal_places=2)
    saldo_pendiente = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Comprobante'
        verbose_name_plural = 'Comprobantes'

    def __str__(self):
        return f"{self.get_tipo_display()} {self.numero} — ${self.importe}"


class FormaPagoOrdenPago(models.Model):
    METODOS = [
        ('transferencia', 'Transferencia bancaria'),
        ('cheque',        'Cheque'),
        ('efectivo',      'Efectivo'),
        ('otro',          'Otro'),
    ]
    orden_pago = models.ForeignKey(OrdenPago, on_delete=models.CASCADE, related_name='formas_pago')
    metodo = models.CharField(max_length=20, choices=METODOS, default='transferencia')
    banco = models.CharField(max_length=100, blank=True, help_text='Banco emisor (transferencia/cheque)')
    cbu = models.CharField(max_length=22, blank=True, help_text='CBU destino (transferencia)')
    numero_cheque = models.CharField(max_length=50, blank=True, help_text='Número de cheque')
    referencia = models.CharField(max_length=100, blank=True, help_text='Nº de transferencia, recibo, etc.')
    importe = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = 'Forma de Pago'
        verbose_name_plural = 'Formas de Pago'

    def __str__(self):
        return f"{self.get_metodo_display()} — ${self.importe}"


class RetencionOrdenPago(models.Model):
    TIPOS = [
        ('iva',        'Retención IVA'),
        ('ganancias',  'Retención Ganancias'),
        ('ingresos_brutos', 'Ingresos Brutos'),
        ('suss',       'SUSS'),
        ('otro',       'Otro'),
    ]
    orden_pago = models.ForeignKey(OrdenPago, on_delete=models.CASCADE, related_name='retenciones')
    tipo = models.CharField(max_length=20, choices=TIPOS, default='iva')
    descripcion = models.CharField(max_length=100, blank=True)
    importe = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = 'Retención'
        verbose_name_plural = 'Retenciones'

    def __str__(self):
        return f"{self.get_tipo_display()} — ${self.importe}"
