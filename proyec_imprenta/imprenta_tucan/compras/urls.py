from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = "compras"

urlpatterns = [
    path("ordenes/", views.lista_ordenes, name="lista_ordenes_compra"),
    path("ordenes/nueva/", views.nueva_orden, name="nueva_orden_compra"),
    path("ordenes/<int:pk>/", views.detalle_orden, name="detalle_orden_compra"),
    path("ordenes/<int:pk>/estado/", views.cambiar_estado_orden, name="cambiar_estado_orden"),
    path("remitos/", views.lista_remitos, name="lista_remitos_compra"),
    path("remitos/nuevo/", views.nuevo_remito, name="nuevo_remito_compra"),
    path("api/solicitud/<int:pk>/items/", views.api_items_solicitud, name="api_items_solicitud"),
    path("insumos/<int:insumo_pk>/precio/", views.actualizar_precio_insumo, name="actualizar_precio_insumo"),
    path("precios/", views.lista_precios_insumos, name="lista_precios_insumos"),
    path("", views.home_compras, name="home_compras"),
    path("comparacion/", views.comparacion_precios, name="comparacion_precios"),
]