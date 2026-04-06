from django.urls import path, include
from django.views.generic import RedirectView
from . import views
from . import views_ordenpago as vop
from insumos import views as insumos_views

app_name = "compras"

urlpatterns = [
    path("ordenes/", views.lista_ordenes, name="lista_ordenes_compra"),
    path("ordenes/nueva/", views.nueva_orden, name="nueva_orden_compra"),
    path("ordenes/<int:pk>/", views.detalle_orden, name="detalle_orden_compra"),
    path("ordenes/<int:pk>/json/", views.detalle_orden_json, name="detalle_orden_json"),
    path("ordenes/<int:pk>/estado/", views.cambiar_estado_orden, name="cambiar_estado_orden"),
    path("ordenes/<int:pk>/enviar-email/", views.enviar_orden_email, name="enviar_orden_email"),
    path("ordenes/<int:pk>/enviar-whatsapp/", views.enviar_orden_whatsapp, name="enviar_orden_whatsapp"),
    # Vistas públicas para proveedores
    path("ordenes/<int:pk>/confirmar/", views.confirmar_orden_publico, name="confirmar_orden_publico"),
    path("ordenes/<int:pk>/rechazar/", views.rechazar_orden_publico, name="rechazar_orden_publico"),
    path("ordenes/<int:pk>/pdf/", views.orden_pdf, name="orden_pdf"),
    path("remitos/", views.lista_remitos, name="lista_remitos_compra"),
    path("remitos/nuevo/", views.nuevo_remito, name="nuevo_remito_compra"),
    path("api/solicitud/<int:pk>/items/", views.api_items_solicitud, name="api_items_solicitud"),
    path("insumos/<int:insumo_pk>/precio/", views.actualizar_precio_insumo, name="actualizar_precio_insumo"),
    path("insumos/<int:insumo_pk>/historial-precios/", views.historial_precios_insumo, name="historial_precios_insumo"),
    path("precios/", views.lista_precios_insumos, name="lista_precios_insumos"),
    path("", views.home_compras, name="home_compras"),
    path("comparacion/", views.comparacion_precios, name="comparacion_precios"),
    path("insumos/<int:insumo_pk>/kardex/", views.kardex_insumo, name="kardex_insumo"),
    path("insumos/<int:insumo_pk>/ajuste/", views.ajuste_stock, name="ajuste_stock"),
    path("api/orden/<int:pk>/items/", views.api_items_orden, name="api_items_orden"),
    path("api/insumo/<int:insumo_pk>/sugerencia/", views.api_insumo_sugerencia, name="api_insumo_sugerencia"),
    
    # CRUD de Insumos integrado en Compras
    path("insumos/", insumos_views.lista_insumos, name="lista_insumos_desde_compras"),
    path("insumos/crear/", insumos_views.crear_insumo, name="crear_insumo_desde_compras"),
    path("insumos/<int:pk>/", insumos_views.detalle_insumo, name="detalle_insumo_desde_compras"),
    path("insumos/<int:pk>/editar/", insumos_views.editar_insumo, name="editar_insumo_desde_compras"),
    path("insumos/<int:pk>/eliminar/", insumos_views.eliminar_insumo, name="eliminar_insumo_desde_compras"),
    path("insumos/<int:pk>/activar/", insumos_views.activar_insumo, name="activar_insumo_desde_compras"),
    path("insumos/<int:pk>/baja/", insumos_views.baja_insumo, name="baja_insumo_desde_compras"),
    
    # Ajuste masivo de precios
    path("ajuste-masivo/", views.ajuste_masivo_precios, name="ajuste_masivo_precios"),

    # Exportar órdenes
    path("ordenes/exportar/", views.exportar_ordenes_excel, name="exportar_ordenes"),

    # Órdenes de Pago
    path("pagos/",                              vop.lista_ordenes_pago,       name="lista_ordenes_pago"),
    path("pagos/nueva/",                        vop.nueva_orden_pago,         name="nueva_orden_pago"),
    path("pagos/<int:pk>/json/",                vop.detalle_orden_pago_json,  name="detalle_orden_pago_json"),
    path("pagos/<int:pk>/aprobar/",             vop.aprobar_orden_pago,       name="aprobar_orden_pago"),
    path("pagos/<int:pk>/registrar-pago/",      vop.registrar_pago,           name="registrar_pago"),
    path("pagos/<int:pk>/anular/",              vop.anular_orden_pago,           name="anular_orden_pago"),
    path("pagos/exportar/",                     vop.exportar_ordenes_pago_excel, name="exportar_ordenes_pago"),
]