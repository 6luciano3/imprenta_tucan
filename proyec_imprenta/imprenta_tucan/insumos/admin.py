from django.contrib import admin
from .models import Insumo


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
