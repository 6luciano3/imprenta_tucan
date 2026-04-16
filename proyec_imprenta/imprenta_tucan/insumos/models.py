import datetime
from django.core.validators import MinValueValidator

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
    proveedor = models.ForeignKey('proveedores.Proveedor', on_delete=models.SET_NULL,
                                  related_name='insumos', null=True, blank=True)
    # DEPRECATED (M-4): usar `stock` en su lugar. Este campo es un remanente del modelo original
    # y no se actualiza en ningún flujo actual. Se mantiene para no romper migraciones existentes.
    cantidad = models.PositiveIntegerField(default=0)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                          validators=[MinValueValidator(0)])
    categoria = models.CharField(max_length=100, blank=True)
    stock = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    stock_minimo_manual = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Stock mínimo sugerido (cargado manualmente). Se usa cuando no hay historial de consumo.',
    )
    cantidad_compra_sugerida = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Cantidad estándar a reponer cuando se detecta necesidad de compra. Reemplaza el dict hardcodeado en tasks.',
    )
    stock_minimo_calculado = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Stock mínimo pre-calculado automáticamente (tarea programada). Evita queries N+1 en listados.',
    )
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
        # Fuente primaria: valor pre-calculado por tarea programada (evita N+1)
        if self.stock_minimo_calculado is not None:
            return self.stock_minimo_calculado
        # Fallback: calcular en tiempo real si no hay cache
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
    FUENTE_MEDIA_MOVIL = 'media_movil'
    FUENTE_ETS = 'ets'
    FUENTE_STOCK_MINIMO = 'stock_minimo'
    FUENTE_FALLBACK = 'fallback'
    FUENTE_CHOICES = [
        (FUENTE_MEDIA_MOVIL, 'Media Móvil Ponderada'),
        (FUENTE_ETS, 'Suavizado Exponencial (ETS)'),
        (FUENTE_STOCK_MINIMO, 'Stock Mínimo Sugerido'),
        (FUENTE_FALLBACK, 'Valor por defecto'),
    ]
    fuente = models.CharField(
        max_length=20, choices=FUENTE_CHOICES,
        default=FUENTE_MEDIA_MOVIL, blank=True,
        help_text='Origen del valor proyectado: algoritmo usado o fallback aplicado.',
    )
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


def predecir_demanda_ets(insumo, periodo_actual, alpha=None):
    from insumos.models import ConsumoRealInsumo
    if alpha is None:
        try:
            from configuracion.models import Parametro
            alpha = float(Parametro.get('DEMANDA_ETS_ALPHA', 0.3))
        except Exception:
            alpha = 0.3
    alpha = max(0.1, min(0.9, alpha))
    anio, mes = map(int, periodo_actual.split('-'))
    periodos = []
    for i in range(12, 0, -1):
        m = mes - i
        y = anio
        while m <= 0:
            m += 12
            y -= 1
        periodos.append(f'{y:04d}-{m:02d}')
    consumos_map = dict(
        ConsumoRealInsumo.objects
        .filter(insumo=insumo, periodo__in=periodos)
        .values_list('periodo', 'cantidad_consumida')
    )
    valores = [float(consumos_map[p]) for p in periodos if p in consumos_map]
    if not valores:
        return None
    if len(valores) == 1:
        return round(valores[0])
    nivel = valores[0]
    for v in valores[1:]:
        nivel = alpha * v + (1 - alpha) * nivel
    return round(nivel)
