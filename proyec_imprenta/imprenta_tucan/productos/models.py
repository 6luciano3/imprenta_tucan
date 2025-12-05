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
    unidadMedida = models.ForeignKey(UnidadMedida, on_delete=models.CASCADE, null=True, blank=True)
    activo = models.BooleanField(default=True)

    # Relación directa: cada producto tiene exactamente una fórmula asociada
    formula = models.ForeignKey('configuracion.Formula', on_delete=models.PROTECT,
                                related_name='productos', help_text="Fórmula para calcular los insumos de este producto")
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

    class Meta:
        unique_together = ('producto', 'insumo')

    def __str__(self):
        return f"{self.producto} -> {self.insumo} x {self.cantidad_por_unidad}"
