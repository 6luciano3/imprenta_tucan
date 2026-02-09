from django.urls import path
from . import views

urlpatterns = [
    path('stock/', views.reporte_stock, name='reporte_stock'),
    path('stock/preview/', views.preview_stock, name='reporte_stock_preview'),

    path('proveedores-activos/', views.reporte_proveedores_activos, name='reporte_proveedores_activos'),
    path('proveedores-activos/preview/', views.preview_proveedores_activos, name='reporte_proveedores_activos_preview'),

    path('clientes-frecuentes/', views.reporte_clientes_frecuentes, name='reporte_clientes_frecuentes'),
    path('clientes-frecuentes/preview/', views.preview_clientes_frecuentes, name='reporte_clientes_frecuentes_preview'),
]
