from django.contrib import admin
from .models import Proveedor, Rubro, ProveedorParametro


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cuit', 'email', 'telefono', 'rubro_nombre', 'activo', 'fecha_creacion')
    list_filter = ('activo', 'rubro_fk')
    search_fields = ('nombre', 'cuit', 'email', 'telefono')
    readonly_fields = ('fecha_creacion',)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Rubro')
    def rubro_nombre(self, obj):
        return obj.rubro_nombre or '-'


@admin.register(Rubro)
class RubroAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo', 'created_at')
    list_filter = ('activo',)
    search_fields = ('nombre',)


@admin.register(ProveedorParametro)
class ProveedorParametroAdmin(admin.ModelAdmin):
    list_display = ('clave', 'valor', 'activo')
    search_fields = ('clave',)
