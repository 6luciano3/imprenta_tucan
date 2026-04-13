from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_facturas, name='lista_facturas'),
    path('<int:pk>/', views.detalle_factura, name='detalle_factura'),
    path('<int:pk>/anular/', views.anular_factura, name='anular_factura'),
    path('pagos/<int:pk>/eliminar/', views.eliminar_pago, name='eliminar_pago'),
]
