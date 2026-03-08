from django.db import models


class EstadoPedido(models.Model):
    nombre = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.nombre


class Pedido(models.Model):
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)
    fecha_pedido = models.DateField(auto_now_add=True)
    fecha_entrega = models.DateField()
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.ForeignKey(EstadoPedido, on_delete=models.CASCADE)
    descuento = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Porcentaje de descuento aplicado al pedido")
    aplicar_iva = models.BooleanField(default=False, help_text="Si se aplica IVA 21% al pedido")


    def __str__(self):
        return f"Pedido {self.id} - {self.cliente}"

    def save(self, *args, **kwargs):
        # Detectar cambio de estado a 'proceso' y descontar stock
        from .services import reservar_insumos_para_pedido
        oferta_aceptada = None
        try:
            from automatizacion.models import OfertaPropuesta
            from decimal import Decimal
            if not self.pk:
                oferta_aceptada = (
                    OfertaPropuesta.objects
                    .filter(cliente=self.cliente, tipo='descuento', estado='aceptada')
                    .order_by('-creada')
                    .first()
                )
                if oferta_aceptada:
                    porcentaje = Decimal(str(oferta_aceptada.parametros.get('descuento', 10)))
                    factor = (Decimal('100') - porcentaje) / Decimal('100')
                    try:
                        self.monto_total = (self.monto_total * factor).quantize(self.monto_total)
                    except Exception:
                        self.monto_total = self.monto_total * factor
        except Exception:
            pass
        estado_proceso = None
        _should_reserve_new = False
        if not self.pk:
            from .models import EstadoPedido
            estado_proceso = EstadoPedido.objects.filter(nombre__icontains='proceso').first()
            if estado_proceso and self.estado == estado_proceso:
                _should_reserve_new = True
        else:
            old = type(self).objects.get(pk=self.pk)
            estado_proceso = self.estado if 'proceso' in self.estado.nombre.lower() else None
            old_estado = old.estado.nombre.lower() if old.estado else None
            new_estado = self.estado.nombre.lower() if self.estado else None
            if 'proceso' not in old_estado and 'proceso' in new_estado:
                reservar_insumos_para_pedido(self)
        super().save(*args, **kwargs)
        if _should_reserve_new:
            reservar_insumos_para_pedido(self)
        try:
            if oferta_aceptada:
                oferta_aceptada.estado = 'aplicada'
                params = oferta_aceptada.parametros or {}
                params['aplicada_pedido_id'] = self.pk
                oferta_aceptada.parametros = params
                oferta_aceptada.save()
        except Exception:
            pass


# NUEVO: Soporte para múltiples productos por pedido
class LineaPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='lineas')
    producto = models.ForeignKey('productos.Producto', on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    especificaciones = models.TextField(blank=True, null=True)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.producto} x {self.cantidad} (Pedido {self.pedido_id})"


class OrdenProduccion(models.Model):
    pedido = models.OneToOneField('Pedido', on_delete=models.CASCADE, related_name='orden_produccion')
    estado = models.CharField(max_length=20, default='pendiente')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OrdenProduccion {self.id} - Pedido {self.pedido.id} ({self.estado})"


class OrdenCompra(models.Model):
    insumo = models.ForeignKey('insumos.Insumo', on_delete=models.CASCADE, to_field='idInsumo')
    cantidad = models.PositiveIntegerField()
    proveedor = models.ForeignKey('proveedores.Proveedor', on_delete=models.CASCADE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=[
        ('sugerida', 'Sugerida'),
        ('confirmada', 'Confirmada'),
        ('rechazada', 'Rechazada'),
    ], default='sugerida')
    comentario = models.TextField(blank=True)
    # Token único para que el proveedor confirme/rechace sin necesidad de login
    token_proveedor = models.CharField(max_length=64, blank=True, unique=True, null=True)
    # Fecha en que el proveedor respondió (confirma o rechaza). Permite medir latencia.
    fecha_respuesta = models.DateTimeField(
        null=True, blank=True,
        help_text='Se asigna automáticamente la primera vez que el estado cambia a confirmada o rechazada.',
    )

    def save(self, *args, **kwargs):
        if not self.token_proveedor:
            import uuid
            self.token_proveedor = uuid.uuid4().hex
        # Registrar fecha de respuesta la primera vez que se confirma o rechaza
        if self.estado in ('confirmada', 'rechazada') and not self.fecha_respuesta:
            from django.utils import timezone
            self.fecha_respuesta = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Orden de compra {self.id} - {self.insumo} ({self.cantidad})"
