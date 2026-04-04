from django.contrib import admin
from .models import Insumo, ProyeccionInsumo, ConsumoRealInsumo


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "categoria", "stock", "precio_unitario", "activo"]
    readonly_fields = ["stock", "precio_unitario"]
    search_fields = ["codigo", "nombre", "categoria"]
    list_filter = ["activo", "tipo", "categoria"]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "stock" in form.base_fields:
            form.base_fields["stock"].help_text = "Solo se modifica desde App Compras > Remitos."
        if "precio_unitario" in form.base_fields:
            form.base_fields["precio_unitario"].help_text = "Solo se modifica desde App Compras > Actualizar Precio."
        return form


@admin.register(ProyeccionInsumo)
class ProyeccionInsumoAdmin(admin.ModelAdmin):
    list_display = ["insumo", "periodo", "cantidad_proyectada", "estado", "fecha_generacion"]
    list_filter = ["estado", "periodo"]
    search_fields = ["insumo__nombre", "insumo__codigo"]
    readonly_fields = ["fecha_generacion", "fecha_validacion"]


@admin.register(ConsumoRealInsumo)
class ConsumoRealInsumoAdmin(admin.ModelAdmin):
    list_display = ["insumo", "periodo", "cantidad_consumida", "fecha_registro", "usuario"]
    list_filter = ["periodo"]
    search_fields = ["insumo__nombre", "insumo__codigo"]
    readonly_fields = ["fecha_registro"]
