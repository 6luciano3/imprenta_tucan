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
    eliminado = models.BooleanField(default=False, help_text="Baja lógica — el registro no se borra físicamente")


    def __str__(self):
        return f"Pedido {self.id} - {self.cliente}"

    def save(self, *args, **kwargs):
        # T-05: lógica de negocio delegada a services.py
        from .services import (
            reservar_insumos_para_pedido,
            devolver_insumos_para_pedido,
            aplicar_descuento_oferta,
            ajustar_score_cancelacion,
            marcar_oferta_aplicada,
            notificar_entrega_pedido,
        )
        oferta_aceptada = None
        _should_reserve_new = False

        if not self.pk:
            # Pedido nuevo: aplicar descuento de oferta si existe
            oferta_aceptada = aplicar_descuento_oferta(self)
            # Si ya nace en estado "proceso", reservar después del super().save()
            estado_proceso = EstadoPedido.objects.filter(nombre__icontains="proceso").first()
            if estado_proceso and self.estado == estado_proceso:
                _should_reserve_new = True
        else:
            old = type(self).objects.get(pk=self.pk)
            old_estado = old.estado.nombre.lower() if old.estado else ""
            new_estado = self.estado.nombre.lower() if self.estado else ""
            if "proceso" not in old_estado and "proceso" in new_estado:
                reservar_insumos_para_pedido(self)
            if "cancelad" in new_estado and "cancelad" not in old_estado:
                ajustar_score_cancelacion(self)
                # Si venía de "En Proceso", devolver el stock consumido
                if "proceso" in old_estado:
                    devolver_insumos_para_pedido(self)
            if "entreg" in new_estado and "entreg" not in old_estado:
                self._notificar_entrega = True   # se dispara en post_save para tener pk seguro

        super().save(*args, **kwargs)

        if _should_reserve_new:
            reservar_insumos_para_pedido(self)
        if oferta_aceptada:
            marcar_oferta_aplicada(self, oferta_aceptada)
        if getattr(self, '_notificar_entrega', False):
            self._notificar_entrega = False
            notificar_entrega_pedido(self)


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
    """
    DEPRECATED (C-6): Este modelo es el usado por el flujo de automatización (pedidos/tasks).
    El modelo completo de compras (con detalles, remitos, estados, pagos) está en
    `compras.models.OrdenCompra`. Todas las referencias nuevas deben apuntar a ese modelo.

    Este modelo se mantiene por compatibilidad con:
      - proveedores/views.py (orden_compra_confirmar / orden_compra_rechazar via token)
      - core/motor/proveedor_engine.py (_latencia_promedio_dias)
      - automatizacion/services.py (enviar_email_orden_compra_proveedor)
    No agregar nuevas funcionalidades aquí.
    """
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


# ─── Signal: registrar ConsumoRealInsumo al completar un pedido ───────────────
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Pedido)
def registrar_consumo_real_al_completar(sender, instance, **kwargs):
    """
    Cuando un pedido pasa a estado 'completado', cruza LineaPedido con
    ProductoInsumo (BOM) y registra el consumo real de cada insumo.
    Evita duplicados: si ya existe un registro para ese pedido+insumo+periodo,
    lo actualiza sumando la diferencia.
    """
    try:
        estado_nombre = instance.estado.nombre.lower() if instance.estado else ""
        if "complet" not in estado_nombre:
            return

        from django.utils import timezone
        from insumos.models import ConsumoRealInsumo
        from productos.models import ProductoInsumo

        periodo = timezone.now().strftime("%Y-%m")
        lineas = instance.lineas.select_related("producto").all()

        for linea in lineas:
            bom = ProductoInsumo.objects.filter(
                producto=linea.producto
            ).select_related("insumo")

            for item in bom:
                if item.es_costo_fijo:
                    cantidad = int(item.cantidad_por_unidad)
                else:
                    cantidad = int(item.cantidad_por_unidad * linea.cantidad)

                if cantidad <= 0:
                    continue

                obj, created = ConsumoRealInsumo.objects.get_or_create(
                    insumo=item.insumo,
                    periodo=periodo,
                    comentario=f"pedido#{instance.pk}",
                    defaults={"cantidad_consumida": cantidad},
                )
                if not created:
                    # Ya existía para este pedido: actualizar
                    obj.cantidad_consumida = cantidad
                    obj.save(update_fields=["cantidad_consumida"])

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"registrar_consumo_real_al_completar: error en pedido #{instance.pk}: {e}"
        )
