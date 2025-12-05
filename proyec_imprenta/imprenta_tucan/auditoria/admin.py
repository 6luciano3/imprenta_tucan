from django.contrib import admin
from .models import AuditEntry


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'app_label', 'model', 'object_id')
    list_filter = ('action', 'app_label', 'model', 'user')
    search_fields = ('object_id', 'object_repr', 'path', 'user__email')
    readonly_fields = ('timestamp', 'user', 'ip_address', 'path', 'method', 'app_label',
                       'model', 'object_id', 'object_repr', 'action', 'changes', 'extra')

    fieldsets = (
        ('Objeto', {
            'fields': ('timestamp', 'action', 'app_label', 'model', 'object_id', 'object_repr')
        }),
        ('Request', {
            'fields': ('user', 'ip_address', 'path', 'method')
        }),
        ('Cambios', {
            'fields': ('changes', 'extra')
        }),
    )
