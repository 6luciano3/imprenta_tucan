from django.contrib import admin
from .models import Rol


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ('nombreRol', 'estado')
    list_filter = ('estado',)
    search_fields = ('nombreRol', 'descripcion')
