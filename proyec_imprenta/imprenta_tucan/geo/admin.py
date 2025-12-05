from django.contrib import admin
from .models import Ciudad


@admin.register(Ciudad)
class CiudadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "provincia", "activo", "actualizado")
    list_filter = ("activo", "provincia")
    search_fields = ("nombre", "provincia")
    readonly_fields = ("creado", "actualizado")
