from django.urls import path
from . import views
from django.views.generic.base import RedirectView

urlpatterns = [
    path('', views.lista_proveedores, name='lista_proveedores'),  # URL raíz /proveedores/
    path('lista/', views.lista_proveedores, name='lista_proveedores_detalle'),
    # Ruta legacy: redirige a la lista unificada preservando querystring
    path('buscar/', RedirectView.as_view(pattern_name='lista_proveedores_detalle',
         permanent=True, query_string=True), name='buscar_proveedor'),
    path('crear/', views.crear_proveedor, name='crear_proveedor'),
    path('detalle/<int:id>/', views.detalle_proveedor, name='detalle_proveedor'),
    path('editar/<int:id>/', views.editar_proveedor, name='editar_proveedor'),
    path('eliminar/<int:id>/', views.eliminar_proveedor, name='eliminar_proveedor'),
    path('activar/<int:id>/', views.activar_proveedor, name='activar_proveedor'),
    path('seed/', views.seed_proveedores_ui, name='seed_proveedores_ui'),
    # Respuesta del proveedor a órdenes de compra (sin login)
    path('orden/<str:token>/confirmar/', views.orden_compra_confirmar, name='orden_compra_confirmar'),
    path('orden/<str:token>/rechazar/', views.orden_compra_rechazar, name='orden_compra_rechazar'),
    # Rubros
    path('alta/rubros/', views.lista_rubros, name='lista_rubros'),
    path('alta/rubros/crear/', views.crear_rubro, name='crear_rubro'),
    path('alta/rubros/editar/<int:pk>/', views.editar_rubro, name='editar_rubro'),
    path('alta/rubros/eliminar/<int:pk>/', views.eliminar_rubro, name='eliminar_rubro'),
]
