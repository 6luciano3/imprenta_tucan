from django.contrib import admin
from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'razon_social', 'email', 'celular', 'estado')
    search_fields = ('nombre', 'apellido', 'razon_social', 'email', 'celular')

    def has_delete_permission(self, request, obj=None):
        return False
