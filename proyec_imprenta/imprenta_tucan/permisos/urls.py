from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_permisos, name='lista_permisos'),
    path('alta/', views.alta_permiso, name='alta_permiso'),
    path('buscar/', views.buscar_permiso, name='buscar_permiso'),
    path('detalle/<int:id>/', views.detalle_permiso, name='detalle_permiso'),
    path('modificar/<int:idPermiso>/', views.modificar_permiso, name='modificar_permiso'),  # Modificación del permiso
    path('baja/<int:idPermiso>/', views.baja_permiso, name='baja_permiso'),
    path('reactivar/<int:idPermiso>/', views.reactivar_permiso, name='reactivar_permiso'),
]
