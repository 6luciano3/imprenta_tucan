from django.db import models
from django.contrib.auth import get_user_model


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
    ESTADOS = [
        ('pendiente', 'Pendiente de aprobación'),
        ('enviada', 'Enviada al cliente'),
        ('aceptada', 'Aceptada por el cliente'),
        ('rechazada', 'Rechazada por el cliente'),
        ('aplicada', 'Aplicada en pedido'),
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
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    periodo = models.CharField(max_length=20, blank=True)  # Período en el que se generó
    score_al_generar = models.FloatField(default=0)
    parametros = models.JSONField(default=dict, blank=True)  # Ej: {"descuento": 10}
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)
    administrador = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True)
    fecha_validacion = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.titulo} - {self.cliente} ({self.estado})"


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
