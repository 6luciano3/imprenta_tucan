import datetime

def predecir_demanda_media_movil(insumo, periodo_actual, meses=3):
    """
    Predice la demanda usando media móvil ponderada de los últimos N meses.

    Los meses más recientes reciben mayor peso:
        mes-1 → peso N,  mes-2 → peso N-1, ..., mes-N → peso 1.

    Si no hay dato para un período, ese período simplemente no aporta peso,
    evitando que promedios bajen artificialmente por datos faltantes.
    """
    from insumos.models import ConsumoRealInsumo
    año, mes = map(int, periodo_actual.split('-'))
    periodos = []
    for i in range(1, meses + 1):
        m = mes - i
        y = año
        if m <= 0:
            m += 12
            y -= 1
        periodos.append(f"{y:04d}-{m:02d}")
    # peso_por_periodo: el período más reciente (periodos[0]) obtiene el mayor peso
    peso_por_periodo = {p: meses - i for i, p in enumerate(periodos)}
    consumos = ConsumoRealInsumo.objects.filter(insumo=insumo, periodo__in=periodos)
    if not consumos.exists():
        return None
    suma_ponderada = sum(c.cantidad_consumida * peso_por_periodo[c.periodo] for c in consumos)
    suma_pesos     = sum(peso_por_periodo[c.periodo] for c in consumos)
    return round(suma_ponderada / suma_pesos) if suma_pesos > 0 else None
from django.db import models
from proveedores.models import Proveedor
from usuarios.models import Usuario


class Insumo(models.Model):
    TIPO_DIRECTO = 'directo'
    TIPO_INDIRECTO = 'indirecto'
    TIPO_CHOICES = [
        (TIPO_DIRECTO, 'Directo'),
        (TIPO_INDIRECTO, 'Indirecto'),
    ]

    @property
    def cantidad_a_reponer(self):
        minimo = self.stock_minimo_sugerido
        actual = self.stock or 0
        return max(0, minimo - actual)
    idInsumo = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    codigo = models.CharField(max_length=20, unique=True)
    proveedor = models.ForeignKey('proveedores.Proveedor', on_delete=models.CASCADE,
                                  related_name='insumos', null=True, blank=True)
    cantidad = models.PositiveIntegerField(default=0)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    categoria = models.CharField(max_length=100, blank=True)
    stock = models.IntegerField(default=0)
    stock_minimo_manual = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Stock mínimo sugerido (cargado manualmente). Se usa cuando no hay historial de consumo.',
    )
    cantidad_compra_sugerida = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Cantidad estándar a reponer cuando se detecta necesidad de compra. Reemplaza el dict hardcodeado en tasks.',
    )
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    unidad_medida = models.CharField(max_length=20, default='unidad', blank=True)
    tipo = models.CharField(
        max_length=10,
        choices=TIPO_CHOICES,
        default=TIPO_DIRECTO,
        help_text='Directo: se incorpora al producto. Indirecto: usado en el proceso pero no en el producto final.'
    )

    @property
    def consumo_promedio_mensual(self):
        # Si hay registros de consumo real, calcular el promedio del último año
        from insumos.models import ConsumoRealInsumo
        from django.utils import timezone
        import datetime
        hace_un_ano = timezone.now() - datetime.timedelta(days=365)
        consumos = ConsumoRealInsumo.objects.filter(insumo=self, fecha_registro__gte=hace_un_ano)
        total = sum(c.cantidad_consumida for c in consumos)
        meses = 12
        return total / meses if total > 0 else 0

    @property
    def stock_minimo_sugerido(self):
        # Si hay historial de consumo, calcularlo dinámicamente
        consumo_mensual = self.consumo_promedio_mensual
        if consumo_mensual > 0:
            try:
                from configuracion.models import Parametro
                dias_reposicion = int(Parametro.get('DIAS_REPOSICION_INSUMO', 15))
            except Exception:
                dias_reposicion = 15
            return round(consumo_mensual * dias_reposicion / 30)
        # Sin historial: usar el mínimo manual cargado
        if self.stock_minimo_manual is not None:
            return self.stock_minimo_manual
        return 0

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nombre}"


class ProyeccionInsumo(models.Model):
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE, to_field='idInsumo')
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
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE, to_field='idInsumo')
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
