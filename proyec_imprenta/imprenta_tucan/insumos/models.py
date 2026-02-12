from django.db import models
from proveedores.models import Proveedor
from usuarios.models import Usuario


class Insumo(models.Model):
    idInsumo = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=20, unique=True)
    proveedor = models.ForeignKey('proveedores.Proveedor', on_delete=models.CASCADE,
                                  related_name='insumos', null=True, blank=True)
    cantidad = models.PositiveIntegerField(default=0)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    categoria = models.CharField(max_length=100, blank=True)
    stock = models.IntegerField(default=0)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nombre}"


class ProyeccionInsumo(models.Model):
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    periodo = models.CharField(max_length=20)  # Ej: '2025-12'
    cantidad_proyectada = models.PositiveIntegerField()
    proveedor_sugerido = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=[
        ('pendiente', 'Pendiente'),
        ('aceptada', 'Aceptada'),
        ('modificada', 'Modificada'),
        ('rechazada', 'Rechazada'),
    ], default='pendiente')
    cantidad_validada = models.PositiveIntegerField(null=True, blank=True)
    proveedor_validado = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name='proyecciones_validadas')
    administrador = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    comentario_admin = models.TextField(blank=True)
    fecha_validacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('insumo', 'periodo')
        verbose_name = 'Proyección de Insumo'
        verbose_name_plural = 'Proyecciones de Insumos'

    def __str__(self):
        return f"{self.insumo} - {self.periodo}: {self.cantidad_proyectada}"

    def comparar_consumo_real(self):
        from .models import ConsumoRealInsumo
        consumos = ConsumoRealInsumo.objects.filter(insumo=self.insumo, periodo=self.periodo)
        if consumos.exists():
            total_consumo = sum([c.cantidad_consumida for c in consumos])
            error = total_consumo - self.cantidad_proyectada
            return {
                'proyectado': self.cantidad_proyectada,
                'real': total_consumo,
                'error': error
            }
        return None


class ConsumoRealInsumo(models.Model):
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    periodo = models.CharField(max_length=20)  # Ej: '2025-12'
    cantidad_consumida = models.PositiveIntegerField()
    fecha_registro = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    comentario = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Consumo Real de Insumo'
        verbose_name_plural = 'Consumos Reales de Insumos'

    def __str__(self):
        return f"{self.insumo} - {self.periodo}: {self.cantidad_consumida}"
