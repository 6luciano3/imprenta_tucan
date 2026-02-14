from django.db import models


class EstadoPedido(models.Model):
    nombre = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.nombre


class Pedido(models.Model):
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)
    producto = models.ForeignKey('productos.Producto', on_delete=models.CASCADE)
    fecha_pedido = models.DateField(auto_now_add=True)
    fecha_entrega = models.DateField()
    cantidad = models.PositiveIntegerField()
    especificaciones = models.TextField(blank=True, null=True)
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.ForeignKey(EstadoPedido, on_delete=models.CASCADE)

    def __str__(self):
        return f"Pedido {self.id} - {self.cliente}"

    def save(self, *args, **kwargs):
        # Detectar cambio de estado a 'proceso' y descontar stock
        from .services import reservar_insumos_para_pedido
        # Aplicar descuento automático si hay oferta aceptada para el cliente (próximo pedido)
        oferta_aceptada = None
        try:
            from automatizacion.models import OfertaPropuesta
            from decimal import Decimal
            # Solo para nuevos pedidos
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
        if not self.pk:
            # Nuevo pedido, buscar el estado 'proceso' si existe
            from .models import EstadoPedido
            estado_proceso = EstadoPedido.objects.filter(nombre__iexact='proceso').first()
        else:
            old = type(self).objects.get(pk=self.pk)
            estado_proceso = self.estado if self.estado.nombre.lower() == 'proceso' else None
            old_estado = old.estado.nombre.lower() if old.estado else None
            new_estado = self.estado.nombre.lower() if self.estado else None
            if old_estado != 'proceso' and new_estado == 'proceso':
                reservar_insumos_para_pedido(self)
        super().save(*args, **kwargs)
        # Marcar oferta como aplicada luego de guardar (si corresponde)
        try:
            if oferta_aceptada:
                oferta_aceptada.estado = 'aplicada'
                params = oferta_aceptada.parametros or {}
                params['aplicada_pedido_id'] = self.pk
                oferta_aceptada.parametros = params
                oferta_aceptada.save()
        except Exception:
            pass


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

    def __str__(self):
        return f"Orden de compra {self.id} - {self.insumo} ({self.cantidad})"
