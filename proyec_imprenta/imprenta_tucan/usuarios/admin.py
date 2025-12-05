from django.contrib import admin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    # Campos visibles en la lista
    list_display = (
        'id',
        'email',
        'nombre',
        'apellido',
        'telefono',
        'rol',
        'is_active',
        'is_staff',
        'is_superuser',
        'last_login',
    )

    # Campos por los que se puede buscar
    search_fields = (
        'email',
        'nombre',
        'apellido',
        'telefono',
        'rol__nombre',  # si rol es FK, permite buscar por nombre del rol
    )

    # Filtros laterales
    list_filter = (
        'rol',
        'is_active',
        'is_staff',
        'is_superuser',
    )

    # Orden por defecto
    ordering = ('-id',)

    # Campos editables directamente en la lista
    list_editable = ('is_active', 'is_staff', 'is_superuser')

    # Campos de solo lectura
    readonly_fields = ('last_login',)

    # Agrupación de campos en el formulario
    fieldsets = (
        ('Datos Personales', {
            'fields': ('nombre', 'apellido', 'email', 'telefono', 'rol')
        }),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Fechas y acceso', {
            'fields': ('last_login',)
        }),
    )
