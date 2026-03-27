from django.utils.crypto import get_random_string
from django.db import models
from django.contrib.auth import get_user_model
from automatizacion.models_feedback import FeedbackRecomendacion  # noqa: F401 — necesario para que Django registre el modelo


class RankingCliente(models.Model):
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)
    score = models.FloatField(default=0)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('cliente',)

    def __str__(self):
        return f"{self.cliente} - Score: {self.score}"


class RankingHistorico(models.Model):
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE, related_name='ranking_historico')
    periodo = models.CharField(max_length=20)  # Ej: '2026-02' o '2026-Q1'
    score = models.FloatField(default=0)
    variacion = models.FloatField(default=0)  # Diferencia respecto del período anterior
    metricas = models.JSONField(default=dict, blank=True)  # Detalle: total_norm, cant_norm, freq_norm, crit_norm
    generado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cliente', 'periodo')

    def __str__(self):
        return f"{self.cliente} - {self.periodo}: {self.score} ({self.variacion:+})"


class ScoreProveedor(models.Model):
    proveedor = models.ForeignKey('proveedores.Proveedor', on_delete=models.CASCADE)
    score = models.FloatField(default=0)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('proveedor',)

    def __str__(self):
        return f"{self.proveedor} - Score: {self.score}"


class OrdenSugerida(models.Model):
    pedido = models.ForeignKey('pedidos.Pedido', on_delete=models.CASCADE, related_name='ordenes_sugeridas')
    insumo = models.ForeignKey('insumos.Insumo', on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    generada = models.DateTimeField(auto_now_add=True)
    confirmada = models.BooleanField(default=False)

    def __str__(self):
        return f"Orden sugerida para {self.insumo} (Pedido {self.pedido.id})"


class OfertaAutomatica(models.Model):
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE, null=True, blank=True)
    descripcion = models.TextField()
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    activa = models.BooleanField(default=True)
    generada = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Oferta para {self.cliente or 'Todos'}: {self.descripcion[:30]}..."


class OfertaPropuesta(models.Model):
    token_email = models.CharField(max_length=32, blank=True, null=True, unique=True)

    ESTADOS = [
        ('pendiente', 'Pendiente de aprobación'),
        ('enviada', 'Enviada al cliente'),
        ('aceptada', 'Aceptada por el cliente'),
        ('rechazada', 'Rechazada por el cliente'),
        ('aplicada', 'Aplicada en pedido'),
        ('vencida', 'Vencida (no respondida a tiempo)'),
        ('aceptada_sin_stock', 'Aceptada – sin stock para pedido automático'),
    ]

    TIPOS = [
        ('descuento', 'Descuento'),
        ('fidelizacion', 'Fidelización'),
        ('prioridad_stock', 'Prioridad en stock'),
        ('promocion', 'Promoción'),
    ]

    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE, related_name='ofertas_propuestas')
    titulo = models.CharField(max_length=120)
    descripcion = models.TextField()
    tipo = models.CharField(max_length=30, choices=TIPOS)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente', db_index=True)
    periodo = models.CharField(max_length=20, blank=True, db_index=True)  # Período en el que se generó
    score_al_generar = models.FloatField(default=0)
    parametros = models.JSONField(default=dict, blank=True)  # Ej: {"descuento": 10}
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)
    administrador = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True)
    fecha_validacion = models.DateTimeField(null=True, blank=True)
    fecha_expiracion = models.DateTimeField(
        null=True, blank=True,
        help_text='Fecha límite para que el cliente responda. Se asigna automáticamente al crear.'
    )

    def save(self, *args, **kwargs):
        # Auto-generar token único para links de email
        if not self.token_email:
            self.token_email = get_random_string(32)
        # Auto-asignar fecha_expiracion si no se indicó (30 días por defecto, configurable)
        if not self.fecha_expiracion and not self.pk:
            try:
                from configuracion.models import Parametro
                dias = int(Parametro.get('OFERTA_DIAS_VIGENCIA', 30))
            except Exception:
                dias = 30
            from django.utils import timezone
            from datetime import timedelta
            self.fecha_expiracion = timezone.now() + timedelta(days=dias)
        super().save(*args, **kwargs)

    @property
    def esta_vencida(self):
        """True si la fecha_expiracion ya pasó y la oferta sigue sin respuesta."""
        from django.utils import timezone
        return (
            self.fecha_expiracion is not None
            and timezone.now() > self.fecha_expiracion
            and self.estado in ('pendiente', 'enviada')
        )

    def __str__(self):
        return f"{self.titulo} - {self.cliente} ({self.estado})"


class MensajeOferta(models.Model):
    ESTADOS = [
        ('enviado', 'Enviado'),
        ('entregado', 'Entregado'),
        ('leido', 'Leído'),
        ('fallido', 'Fallido'),
    ]

    CANALES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
    ]

    oferta = models.ForeignKey(OfertaPropuesta, on_delete=models.CASCADE, related_name='mensajes')
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE)
    estado = models.CharField(max_length=20, choices=ESTADOS)
    canal = models.CharField(max_length=20, choices=CANALES, default='email')
    provider_id = models.CharField(max_length=120, blank=True)
    detalle = models.TextField(blank=True)
    enviado_en = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-actualizado',)

    def __str__(self):
        return f"Mensaje {self.get_estado_display()} ({self.canal}) - Oferta {self.oferta_id}"


class AccionCliente(models.Model):
    TIPOS = [
        ('vista', 'Vista de oferta/listado'),
        ('click', 'Click en enlace/botón'),
        ('aceptar', 'Aceptó la oferta'),
        ('rechazar', 'Rechazó la oferta'),
        ('consulta', 'Realizó una consulta'),
        ('leido', 'Leyó el mensaje'),
    ]

    CANALES = [
        ('web', 'Web'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
    ]

    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE, related_name='acciones_cliente')
    oferta = models.ForeignKey(OfertaPropuesta, on_delete=models.CASCADE, null=True, blank=True, related_name='acciones_cliente')
    tipo = models.CharField(max_length=20, choices=TIPOS, db_index=True)
    canal = models.CharField(max_length=20, choices=CANALES, default='web')
    detalle = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    creado = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-creado',)

    def __str__(self):
        return f"Acción {self.tipo} ({self.canal}) - Cliente {self.cliente_id} Oferta {self.oferta_id}"


class AprobacionAutomatica(models.Model):
    pedido = models.ForeignKey('pedidos.Pedido', on_delete=models.CASCADE)
    aprobado_por = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True)
    aprobado = models.BooleanField(default=False)
    fecha_aprobacion = models.DateTimeField(auto_now_add=True)
    comentario = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Aprobación de Pedido {self.pedido.id}: {'Sí' if self.aprobado else 'No'}"


class AutomationLog(models.Model):
    evento = models.CharField(max_length=100)
    descripcion = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True)
    datos = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"{self.evento} - {self.fecha}"


# --- Automatización de presupuestos con criterios ponderados ---
class ConsultaStockProveedor(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('disponible', 'Disponible'),
        ('parcial', 'Parcialmente disponible'),
        ('no', 'No disponible'),
        ('error', 'Error de consulta'),
    ]

    proveedor = models.ForeignKey('proveedores.Proveedor', on_delete=models.CASCADE)
    insumo = models.ForeignKey('insumos.Insumo', on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    respuesta = models.JSONField(default=dict, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Consulta {self.proveedor} / {self.insumo} ({self.cantidad}) - {self.estado}"


class CompraPropuesta(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('consultado', 'Consulta enviada'),
        ('respuesta_disponible', 'Respuesta disponible'),
        ('parcial', 'Disponibilidad parcial'),
        ('no_disponible', 'No disponible'),
        ('aceptada', 'Aceptada'),
        ('rechazada', 'Rechazada'),
        ('modificada', 'Modificada'),
    ]

    TRIGGER = [
        ('faltante_stock', 'Faltante de stock'),
        ('pedido_mayor_stock', 'Pedido supera stock'),
        ('stock_minimo_vencido', 'Stock mínimo vencido'),
    ]

    insumo = models.ForeignKey('insumos.Insumo', on_delete=models.CASCADE)
    cantidad_requerida = models.PositiveIntegerField()
    proveedor_recomendado = models.ForeignKey('proveedores.Proveedor', on_delete=models.SET_NULL, null=True, blank=True)
    pesos_usados = models.JSONField(default=dict, blank=True)  # {'precio':0.4,'cumplimiento':0.3,...}
    motivo_trigger = models.CharField(max_length=30, choices=TRIGGER)
    estado = models.CharField(max_length=30, choices=ESTADOS, default='pendiente', db_index=True)
    borrador_oc = models.ForeignKey('pedidos.OrdenCompra', on_delete=models.SET_NULL, null=True, blank=True)
    consulta_stock = models.ForeignKey(ConsultaStockProveedor, on_delete=models.SET_NULL, null=True, blank=True)
    administrador = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True)
    decision = models.CharField(max_length=20, blank=True)  # 'aceptar'|'rechazar'|'modificar'
    comentario_admin = models.TextField(blank=True)
    feedback_pesos = models.JSONField(default=dict, blank=True)  # {'precio':+0.05,'cumplimiento':-0.05,...}
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Propuesta {self.insumo} x {self.cantidad_requerida} - {self.estado}"


class SolicitudCotizacion(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente de respuesta'),
        ('respondida', 'Respondida por proveedor'),
        ('confirmada', 'Confirmada'),
        ('rechazada', 'Rechazada'),
        ('vencida', 'Vencida'),
    ]
    proveedor = models.ForeignKey('proveedores.Proveedor', on_delete=models.CASCADE, related_name='solicitudes_cotizacion')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente', db_index=True)
    token = models.CharField(max_length=64, unique=True, blank=True)
    comentario = models.TextField(blank=True)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.token:
            import uuid
            self.token = uuid.uuid4().hex + uuid.uuid4().hex[:32]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"SC-{self.id:04d} | {self.proveedor.nombre} | {self.estado}"


class SolicitudCotizacionItem(models.Model):
    solicitud = models.ForeignKey(SolicitudCotizacion, on_delete=models.CASCADE, related_name='items')
    insumo = models.ForeignKey('insumos.Insumo', on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    precio_unitario_respuesta = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    disponible = models.BooleanField(null=True, blank=True)
    observacion = models.TextField(blank=True)

    def __str__(self):
        return f"{self.insumo.nombre} x {self.cantidad}"


class EmailTracking(models.Model):
    """Tracking de emails enviados a clientes para medir apertura y clicks."""
    TIPOS = [
        ('cliente_inactivo', 'Cliente Inactivo'),
        ('presupuesto_recordatorio', 'Recordatorio Presupuesto'),
        ('oferta', 'Oferta Comercial'),
    ]
    
    ESTADOS = [
        ('enviado', 'Enviado'),
        ('abierto', 'Abierto'),
        ('clickeado', 'Clickeado'),
        ('respondido', 'Respondido'),
    ]

    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE, related_name='email_tracking')
    tipo = models.CharField(max_length=30, choices=TIPOS)
    token = models.CharField(max_length=64, unique=True)
    email_enviado = models.EmailField()
    asunto = models.CharField(max_length=200)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='enviado')
    enviado_en = models.DateTimeField(auto_now_add=True)
    abierto_en = models.DateTimeField(null=True, blank=True)
    clickeado_en = models.DateTimeField(null=True, blank=True)
    respondido_en = models.DateTimeField(null=True, blank=True)
    respuesta_texto = models.TextField(blank=True, default='')

    def __str__(self):
        return f"Tracking {self.tipo} - {self.cliente.email} ({self.estado})"


class RespuestaCliente(models.Model):
    """Registro de respuestas de clientes a emails enviados."""
    TIPOS = [
        ('cliente_inactivo', 'Cliente Inactivo'),
        ('presupuesto_recordatorio', 'Recordatorio Presupuesto'),
    ]

    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE, related_name='respuestas')
    tipo = models.CharField(max_length=30, choices=TIPOS)
    email_origen = models.EmailField()
    mensaje = models.TextField()
    recibido_en = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)
    leida_en = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Respuesta de {self.cliente.email} - {self.recibido_en.strftime('%d/%m/%Y')}"
