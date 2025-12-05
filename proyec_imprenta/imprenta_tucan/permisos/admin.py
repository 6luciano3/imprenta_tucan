from django.contrib import admin
from .models import Permiso


@admin.register(Permiso)
class PermisoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'modulo', 'estado')
    list_filter = ('estado', 'modulo')
    search_fields = ('nombre', 'descripcion', 'modulo')
