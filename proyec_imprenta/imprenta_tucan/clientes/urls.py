from django.urls import path
from . import views
from django.views.generic.base import RedirectView


urlpatterns = [
    # Crear/alta
    path('alta/', views.alta_cliente, name='alta_cliente'),
    path('crear/', views.alta_cliente, name='crear_cliente'),

    # Listado y búsqueda
    path('lista/', views.lista_clientes, name='lista_clientes'),
    # RUTA LEGACY: redirige a la lista unificada preservando querystring
    path('buscar/', RedirectView.as_view(pattern_name='lista_clientes',
         permanent=True, query_string=True), name='buscar_cliente'),

    # Detalle y edición
    path('detalle/<int:id>/', views.detalle_cliente, name='detalle_cliente'),
    path('editar/<int:id>/', views.editar_cliente, name='editar_cliente'),

    # Activación/Desactivación
    path('activar/<int:id>/', views.activar_cliente, name='activar_cliente'),

    # Eliminación
    path('eliminar/<int:id>/', views.eliminar_cliente, name='eliminar_cliente'),
    path('confirmar-eliminacion/<int:id>/', views.confirmar_eliminacion_cliente, name='confirmar_eliminacion_cliente'),
]
