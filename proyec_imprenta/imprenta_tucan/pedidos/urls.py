from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_pedidos, name='lista_pedidos'),
    path('alta/', views.alta_pedido, name='alta_pedido'),
    path('verificar-stock/', views.verificar_stock, name='verificar_stock'),
    path('verificar-stock-modificar/<int:idPedido>/', views.verificar_stock_modificar, name='verificar_stock_modificar'),
    path('buscar/', views.buscar_pedido, name='buscar_pedido'),
    path('detalle/<int:pk>/', views.detalle_pedido, name='detalle_pedido'),
    path('modificar/<int:idPedido>/', views.modificar_pedido, name='modificar_pedido'),
    path('eliminar/<int:idPedido>/', views.eliminar_pedido, name='eliminar_pedido'),
]
