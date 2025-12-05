from .models import GrupoParametro, Parametro, FeatureFlag, ListaConfig
from django.contrib import admin
from .models import UnidadDeMedida


@admin.register(UnidadDeMedida)
class UnidadDeMedidaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'simbolo', 'activo')
    search_fields = ('nombre', 'simbolo')


@admin.register(GrupoParametro)
class GrupoParametroAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre")
    search_fields = ("codigo", "nombre")


@admin.register(Parametro)
class ParametroAdmin(admin.ModelAdmin):
    list_display = ("codigo", "grupo", "tipo", "activo", "editable")
    list_filter = ("grupo", "tipo", "activo", "editable")
    search_fields = ("codigo", "nombre", "descripcion")
    readonly_fields = ("creado", "actualizado")
    fieldsets = (
        (None, {"fields": ("codigo", "grupo", "nombre", "descripcion")}),
        ("Valor", {"fields": ("tipo", "valor")}),
        ("Estado", {"fields": ("activo", "editable", "creado", "actualizado")}),
    )


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("codigo", "activo", "actualizado")
    list_filter = ("activo",)
    search_fields = ("codigo", "descripcion")
    readonly_fields = ("creado", "actualizado")


@admin.register(ListaConfig)
class ListaConfigAdmin(admin.ModelAdmin):
    list_display = ("codigo", "page_size", "orden_default", "activo")
    list_filter = ("activo",)
    search_fields = ("codigo", "descripcion")
    readonly_fields = ("actualizado",)
    fieldsets = (
        (None, {"fields": ("codigo", "descripcion", "activo")}),
        (
            "Listado",
            {
                "fields": (
                    "page_size",
                    "max_page_size",
                    "orden_default",
                    "columnas_visibles",
                )
            },
        ),
        ("Meta", {"fields": ("actualizado",)}),
    )
