from django.contrib import admin
from .models import CategoriaProducto, TipoProducto, UnidadMedida, Producto, ProductoInsumo


@admin.register(CategoriaProducto)
class CategoriaProductoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombreCategoria", "descripcion")
    search_fields = ("nombreCategoria",)


@admin.register(TipoProducto)
class TipoProductoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombreTipoProducto", "descripcion")
    search_fields = ("nombreTipoProducto",)


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ("id", "nombreUnidad", "abreviatura")
    search_fields = ("nombreUnidad", "abreviatura")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        "idProducto", "nombreProducto", "precioUnitario", "categoriaProducto",
        "tipoProducto", "unidadMedida", "tinta_insumo", "activo",
    )
    list_filter = ("categoriaProducto", "tipoProducto", "unidadMedida", "activo")
    search_fields = ("nombreProducto",)
    fieldsets = (
        (None, {"fields": ("nombreProducto", "descripcion", "precioUnitario",
         "categoriaProducto", "tipoProducto", "unidadMedida", "activo")}),
        ("Cálculo de insumos", {"fields": ("formula", "tinta_insumo")}),
    )


@admin.register(ProductoInsumo)
class ProductoInsumoAdmin(admin.ModelAdmin):
    list_display = ("producto", "insumo", "cantidad_por_unidad")
    list_filter = ("producto", "insumo")
    search_fields = ("producto__nombreProducto", "insumo__nombre", "insumo__codigo")
