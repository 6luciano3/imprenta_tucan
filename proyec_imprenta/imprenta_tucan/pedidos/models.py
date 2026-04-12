import logging

from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


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
                # Devolver stock si el pedido ya había consumido insumos.
                # Ocurre cuando venía de En Proceso, Completado o Entregado
                # (en todos esos estados el stock fue reservado al pasar por "proceso").
                _estados_con_stock_reservado = ("proceso", "complet", "entreg")
                if any(s in old_estado for s in _estados_con_stock_reservado):
                    devolver_insumos_para_pedido(self)
            if "entreg" in new_estado and "entreg" not in old_estado:
                self._notificar_entrega = True   # se dispara en post_save para tener pk seguro
                self._emitir_factura = True

        super().save(*args, **kwargs)

        if _should_reserve_new:
            reservar_insumos_para_pedido(self)
        if oferta_aceptada:
            marcar_oferta_aplicada(self, oferta_aceptada)
        if getattr(self, '_notificar_entrega', False):
            self._notificar_entrega = False
            notificar_entrega_pedido(self)
        if getattr(self, '_emitir_factura', False):
            self._emitir_factura = False
            try:
                from .services import crear_factura_para_pedido
                crear_factura_para_pedido(self)
            except Exception:
                logger.exception('Error al emitir factura para pedido #%s', self.pk)


class Factura(models.Model):
    """Factura emitida automáticamente cuando un Pedido pasa a estado Entregado."""
    pedido = models.OneToOneField(
        Pedido, on_delete=models.CASCADE, related_name='factura'
    )
    numero = models.CharField(
        max_length=20, unique=True,
        help_text='Número correlativo. Formato: F-YYYY-NNNN',
    )
    fecha_emision = models.DateTimeField(default=timezone.now)
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ['-fecha_emision']
        verbose_name = 'Factura'
        verbose_name_plural = 'Facturas'

    def __str__(self):
        return f'Factura {self.numero} — Pedido #{self.pedido_id}'

    @classmethod
    def proximo_numero(cls, punto_venta: int = 1):
        """
        Genera el siguiente número correlativo en formato AFIP: XXXX-XXXXXXXX
        Ejemplo: 0001-00000001
        """
        pv = f'{punto_venta:04d}'
        ultimo = (
            cls.objects.filter(numero__startswith=f'{pv}-')
            .order_by('-numero')
            .first()
        )
        if ultimo:
            try:
                secuencia = int(ultimo.numero.split('-')[-1]) + 1
            except (ValueError, IndexError):
                secuencia = 1
        else:
            secuencia = 1
        return f'{pv}-{secuencia:08d}'

    @property
    def total_pagado(self):
        from django.db.models import Sum
        resultado = self.pagos.aggregate(total=Sum('monto'))['total']
        return resultado or 0

    @property
    def saldo_pendiente(self):
        return self.monto_total - self.total_pagado

    @property
    def estado_pago(self):
        """Retorna: 'pagada', 'parcial' o 'pendiente'."""
        pagado = self.total_pagado
        if pagado <= 0:
            return 'pendiente'
        if pagado >= self.monto_total:
            return 'pagada'
        return 'parcial'

    @property
    def estado_pago_display(self):
        return {
            'pagada': 'Pagada',
            'parcial': 'Pago parcial',
            'pendiente': 'Pendiente',
        }.get(self.estado_pago, 'Pendiente')


class PagoFactura(models.Model):
    """Registro de un pago (total o parcial) sobre una Factura."""

    METODO_CHOICES = [
        ('efectivo',        'Efectivo'),
        ('transferencia',   'Transferencia bancaria'),
        ('cheque',          'Cheque'),
        ('tarjeta_debito',  'Tarjeta de débito'),
        ('tarjeta_credito', 'Tarjeta de crédito'),
        ('otro',            'Otro'),
    ]

    factura = models.ForeignKey(
        Factura, on_delete=models.CASCADE, related_name='pagos'
    )
    fecha_pago = models.DateField(default=timezone.now)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo_pago = models.CharField(
        max_length=20, choices=METODO_CHOICES, default='efectivo'
    )
    referencia = models.CharField(
        max_length=100, blank=True,
        help_text='Nro. de transferencia, cheque, etc. (opcional)',
    )
    notas = models.TextField(blank=True)
    registrado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha_pago', 'registrado_en']
        verbose_name = 'Pago de Factura'
        verbose_name_plural = 'Pagos de Facturas'

    def __str__(self):
        return f'Pago ${self.monto} — {self.factura.numero} ({self.get_metodo_pago_display()})'


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
    DEPRECATED — NO AGREGAR NUEVAS FUNCIONALIDADES AQUÍ.

    Este modelo simple fue el original. El modelo completo (con detalles, remitos,
    estados FK, pagos, historial de precios) vive en `compras.models.OrdenCompra`.

    Se mantiene únicamente por compatibilidad con:
      - automatizacion/models.py  → CompraPropuesta.borrador_oc (FK a este modelo)
      - automatizacion/tasks.py   → crea instancias de este modelo al disparar compras automáticas
      - automatizacion/services.py → enviar_email_orden_compra_proveedor
      - proveedores/views.py      → confirmar/rechazar orden por token (flujo automático)
      - core/motor/proveedor_engine.py → _latencia_promedio_dias

    PLAN DE MIGRACIÓN:
      1. Migrar CompraPropuesta.borrador_oc → FK a compras.OrdenCompra
      2. Refactorizar automatizacion/tasks.py para crear compras.OrdenCompra con detalles
      3. Migrar automatizacion/services.py para usar compras.OrdenCompra
      4. Actualizar proveedores/views.py para usar compras.OrdenCompra (ya tiene token_proveedor)
      5. Una vez sin referencias, eliminar este modelo con una migración
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

    except Exception:
        logger.exception(
            "registrar_consumo_real_al_completar: error inesperado en pedido #%s — "
            "el historial de consumo puede estar incompleto.",
            instance.pk,
        )
        # Notificar al administrador si hay email configurado
        try:
            from django.core.mail import mail_admins
            mail_admins(
                subject=f"[Imprenta Tucán] Error en consumo real — Pedido #{instance.pk}",
                message=(
                    f"El signal registrar_consumo_real_al_completar falló para el "
                    f"Pedido #{instance.pk}.\n\n"
                    f"El historial de consumo de insumos puede estar incompleto.\n"
                    f"Revisá los logs del servidor para más detalles."
                ),
                fail_silently=True,
            )
        except Exception:
            pass  # mail_admins es best-effort, no debe romper nada
