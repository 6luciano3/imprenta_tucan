from django.contrib import admin
from .models import RankingCliente, RankingHistorico, OfertaAutomatica, OfertaPropuesta, OrdenSugerida, AprobacionAutomatica, AutomationLog, ScoreProveedor

@admin.register(RankingCliente)
class RankingClienteAdmin(admin.ModelAdmin):
    list_display = ("cliente", "score", "actualizado")
    search_fields = ("cliente__apellido", "cliente__nombre", "cliente__razon_social")
    list_filter = ("actualizado",)

@admin.register(RankingHistorico)
class RankingHistoricoAdmin(admin.ModelAdmin):
    list_display = ("cliente", "periodo", "score", "variacion", "generado")
    search_fields = ("cliente__apellido", "cliente__nombre", "periodo")
    list_filter = ("periodo",)

@admin.register(OfertaPropuesta)
class OfertaPropuestaAdmin(admin.ModelAdmin):
    list_display = ("cliente", "titulo", "tipo", "estado", "periodo", "score_al_generar", "creada")
    search_fields = ("cliente__apellido", "cliente__nombre", "titulo")
    list_filter = ("estado", "tipo", "periodo")

@admin.register(OfertaAutomatica)
class OfertaAutomaticaAdmin(admin.ModelAdmin):
    list_display = ("cliente", "descripcion", "fecha_inicio", "fecha_fin", "activa", "generada")
    list_filter = ("activa",)

@admin.register(OrdenSugerida)
class OrdenSugeridaAdmin(admin.ModelAdmin):
    list_display = ("pedido", "insumo", "cantidad", "generada", "confirmada")

@admin.register(AprobacionAutomatica)
class AprobacionAutomaticaAdmin(admin.ModelAdmin):
    list_display = ("pedido", "aprobado_por", "aprobado", "fecha_aprobacion")

@admin.register(AutomationLog)
class AutomationLogAdmin(admin.ModelAdmin):
    list_display = ("evento", "fecha", "usuario")
    search_fields = ("evento",)

@admin.register(ScoreProveedor)
class ScoreProveedorAdmin(admin.ModelAdmin):
    list_display = ("proveedor", "score", "actualizado")
