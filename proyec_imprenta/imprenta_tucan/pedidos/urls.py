from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_pedidos, name='lista_pedidos'),
    path('alta/', views.alta_pedido, name='alta_pedido'),
    path('verificar-stock/', views.verificar_stock, name='verificar_stock'),
    path('verificar-stock-modificar/<int:idPedido>/', views.verificar_stock_modificar, name='verificar_stock_modificar'),
    path('verificar-stock-diferencial/<int:idPedido>/', views.verificar_stock_diferencial, name='verificar_stock_diferencial'),
    path('enviar-cliente/<int:idPedido>/', views.enviar_pedido_cliente, name='enviar_pedido_cliente'),
    path('factura/<int:idPedido>/pdf/', views.descargar_factura, name='descargar_factura'),
    path('buscar/', views.buscar_pedido, name='buscar_pedido'),
    path('detalle/<int:pk>/', views.detalle_pedido, name='detalle_pedido'),
    path('modificar/<int:idPedido>/', views.modificar_pedido, name='modificar_pedido'),
    path('eliminar/<int:idPedido>/', views.eliminar_pedido, name='eliminar_pedido'),
    path('cambiar-estado/<int:idPedido>/', views.cambiar_estado_pedido, name='cambiar_estado_pedido'),
    path('orden-compra/<int:pk>/', views.orden_compra_detalle, name='orden_compra_detalle'),
    path('exportar/', views.exportar_pedidos_csv, name='exportar_pedidos'),
    path('<int:pk>/clonar/', views.clonar_pedido, name='clonar_pedido'),
]
