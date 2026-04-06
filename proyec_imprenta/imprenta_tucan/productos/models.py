# productos/models.py
from django.db import models


class CategoriaProducto(models.Model):
    nombreCategoria = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombreCategoria


class TipoProducto(models.Model):
    nombreTipoProducto = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombreTipoProducto


class UnidadMedida(models.Model):
    nombreUnidad = models.CharField(max_length=50)
    abreviatura = models.CharField(max_length=10)

    def __str__(self):
        return self.nombreUnidad


class Producto(models.Model):
    @property
    def tipo(self):
        """Compatibilidad para estrategias: retorna el nombre del tipo de producto en minúsculas o 'folleto' por defecto."""
        if self.tipoProducto and hasattr(self.tipoProducto, 'nombreTipoProducto'):
            return self.tipoProducto.nombreTipoProducto.lower()
        return 'folleto'
    @property
    def papel_insumo(self):
        # Devuelve el insumo de papel asociado, si existe (dummy)
        return getattr(self, '_papel_insumo', None) or "-"

    @property
    def unidades_por_pliego(self):
        # Devuelve unidades por pliego (dummy)
        return getattr(self, '_unidades_por_pliego', None) or "-"

    @property
    def merma_papel(self):
        # Devuelve la merma de papel (dummy)
        return getattr(self, '_merma_papel', None) or "-"

    @property
    def gramos_por_pliego(self):
        # Devuelve gramos por pliego (dummy)
        return getattr(self, '_gramos_por_pliego', None) or "-"

    @property
    def merma_tinta(self):
        # Devuelve la merma de tinta (dummy)
        return getattr(self, '_merma_tinta', None) or "-"
    idProducto = models.AutoField(primary_key=True)
    nombreProducto = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    precioUnitario = models.DecimalField(max_digits=10, decimal_places=2)
    categoriaProducto = models.ForeignKey(CategoriaProducto, on_delete=models.CASCADE, null=True, blank=True)
    tipoProducto = models.ForeignKey(TipoProducto, on_delete=models.CASCADE, null=True, blank=True)
    unidadMedida = models.ForeignKey('configuracion.UnidadDeMedida', on_delete=models.SET_NULL, null=True, blank=True)
    activo = models.BooleanField(default=True)

    # Relación directa: cada producto puede tener una fórmula asociada (opcional)
    formula = models.ForeignKey('configuracion.Formula', on_delete=models.SET_NULL,
                                null=True, blank=True,
                                related_name='productos', help_text="Fórmula para calcular los insumos de este producto (opcional)")
    tinta_insumo = models.ForeignKey(
        'insumos.Insumo', on_delete=models.SET_NULL, null=True, blank=True, related_name='productos_tinta',
        help_text="Insumo de tinta a descontar (gramos)"
    )

    # Compatibilidad hacia atrás con código existente que usa 'precio'
    @property
    def precio(self):
        return self.precioUnitario

    def __str__(self):
        return self.nombreProducto


class ProductoInsumo(models.Model):
    """Define la receta/BOM: cuánto insumo se necesita por 1 unidad de producto."""
    producto = models.ForeignKey(
        Producto, on_delete=models.CASCADE, related_name="receta"
    )
    insumo = models.ForeignKey(
        'insumos.Insumo', on_delete=models.CASCADE, related_name='usos'
    )
    cantidad_por_unidad = models.DecimalField(
        max_digits=10, decimal_places=3, help_text="Cantidad requerida por unidad de producto"
    )
    es_costo_fijo = models.BooleanField(
        default=False,
        help_text="Si es True, la cantidad es fija por trabajo (no se multiplica por la cantidad pedida). Usar para planchas, fotolitos y similares."
    )

    class Meta:
        unique_together = ('producto', 'insumo')

    def __str__(self):
        return f"{self.producto} -> {self.insumo} x {self.cantidad_por_unidad}"




class ParametroProducto(models.Model):
    """Parametros tecnicos del producto para calcular insumos.
    Basados en la formula: CD = Papel + Tinta + Planchas + Barniz + Laminado
    """
    producto = models.OneToOneField(
        "Producto", on_delete=models.CASCADE, related_name="parametros_tecnicos"
    )
    # Produccion
    R = models.DecimalField(max_digits=8, decimal_places=2, default=1,
        help_text="Rendimiento: unidades por pliego")
    M = models.DecimalField(max_digits=5, decimal_places=4, default=0.05,
        help_text="Merma (ej: 0.05 = 5%)")
    C = models.PositiveSmallIntegerField(default=4,
        help_text="Cantidad de colores (1=B/N, 4=CMYK)")
    F = models.PositiveSmallIntegerField(default=1,
        help_text="Caras impresas (1 o 2)")
    Formas = models.PositiveSmallIntegerField(default=1,
        help_text="Cantidad de formas de impresion")
    # Papel
    ancho_pliego_cm = models.DecimalField(max_digits=6, decimal_places=2, default=70)
    alto_pliego_cm = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    gramaje = models.DecimalField(max_digits=6, decimal_places=2, default=130,
        help_text="Gramaje del papel en g/m2")
    # Tinta
    At = models.DecimalField(max_digits=8, decimal_places=4, default=0.06,
        help_text="Area impresa por unidad en m2")
    Ct = models.DecimalField(max_digits=6, decimal_places=2, default=1.5,
        help_text="Consumo promedio gr/m2 por color")
    # Barniz (opcional)
    tiene_barniz = models.BooleanField(default=False)
    Cb = models.DecimalField(max_digits=6, decimal_places=2, default=0,
        help_text="Consumo gr/m2 barniz")
    # Laminado (opcional)
    tiene_laminado = models.BooleanField(default=False)
    Plam = models.DecimalField(max_digits=8, decimal_places=4, default=0,
        help_text="Precio por m2 laminado")

    class Meta:
        verbose_name = "Parametros Tecnicos del Producto"

    def __str__(self):
        return f"Params: {self.producto.nombreProducto}"


class RecetaDinamica(models.Model):
    """Receta completa de un producto con multiples lineas de insumos."""
    producto = models.OneToOneField(
        "Producto", on_delete=models.CASCADE, related_name="receta_dinamica"
    )
    activo = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    notas = models.TextField(blank=True)

    class Meta:
        verbose_name = "Receta Dinamica"
        verbose_name_plural = "Recetas Dinamicas"

    def __str__(self):
        return f"Receta: {self.producto.nombreProducto} v{self.version}"

    def calcular(self, cantidad: int) -> dict:
        """Retorna dict {insumo_id: cantidad_requerida} para Q unidades."""
        resultado = {}
        for linea in self.lineas.select_related("insumo").filter(activo=True):
            qty = linea.calcular(cantidad)
            if qty and qty > 0:
                if linea.insumo_id in resultado:
                    resultado[linea.insumo_id] += qty
                else:
                    resultado[linea.insumo_id] = qty
        return resultado


class LineaReceta(models.Model):
    """Una linea de la receta: define cuanto insumo se necesita para Q unidades."""
    TIPO_PAPEL    = "papel"
    TIPO_TINTA    = "tinta"
    TIPO_PLANCHA  = "plancha"
    TIPO_BARNIZ   = "barniz"
    TIPO_LAMINADO = "laminado"
    TIPO_OTRO     = "otro"
    TIPO_CHOICES  = [
        (TIPO_PAPEL,    "Papel"),
        (TIPO_TINTA,    "Tinta"),
        (TIPO_PLANCHA,  "Plancha"),
        (TIPO_BARNIZ,   "Barniz"),
        (TIPO_LAMINADO, "Laminado"),
        (TIPO_OTRO,     "Otro"),
    ]

    receta  = models.ForeignKey(RecetaDinamica, on_delete=models.CASCADE, related_name="lineas")
    insumo  = models.ForeignKey("insumos.Insumo", on_delete=models.PROTECT, related_name="lineas_receta")
    tipo    = models.CharField(max_length=10, choices=TIPO_CHOICES)
    activo  = models.BooleanField(default=True)
    orden   = models.PositiveSmallIntegerField(default=0)
    notas   = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["orden", "tipo"]
        verbose_name = "Linea de Receta"
        verbose_name_plural = "Lineas de Receta"

    def __str__(self):
        return f"{self.receta.producto.nombreProducto} | {self.tipo} | {self.insumo.nombre}"

    def calcular(self, Q: int):
        """Aplica la formula del tipo correspondiente usando ParametroProducto."""
        import math
        from decimal import Decimal
        try:
            p = self.receta.producto.parametros_tecnicos
        except Exception:
            return Decimal(0)

        Q  = Decimal(Q)
        R  = Decimal(p.R)
        M  = Decimal(p.M)
        C  = Decimal(p.C)
        F  = Decimal(p.F)
        Fo = Decimal(p.Formas)
        At = Decimal(p.At)
        Ct = Decimal(p.Ct)
        Cb = Decimal(p.Cb)

        if self.tipo == self.TIPO_PAPEL:
            # Pliegos = (Q / R) * (1 + M)
            # Resultado en pliegos
            pliegos = (Q / R) * (1 + M)
            return Decimal(math.ceil(pliegos))

        elif self.tipo == self.TIPO_TINTA:
            # Consumo_Tinta_kg = (Q * At * Ct * C * F) / 1000
            gramos = Q * At * Ct * C * F
            return (gramos / 1000).quantize(Decimal("0.001"))

        elif self.tipo == self.TIPO_PLANCHA:
            # Planchas = C * F * Formas (fijo por trabajo, no por cantidad)
            return C * F * Fo

        elif self.tipo == self.TIPO_BARNIZ:
            # Consumo_Barniz_kg = (Q * At * Cb) / 1000
            if not p.tiene_barniz:
                return Decimal(0)
            gramos = Q * At * Cb
            return (gramos / 1000).quantize(Decimal("0.001"))

        elif self.tipo == self.TIPO_LAMINADO:
            # Costo_Laminado = Q * At (en m2)
            if not p.tiene_laminado:
                return Decimal(0)
            return (Q * At).quantize(Decimal("0.001"))

        return Decimal(0)
