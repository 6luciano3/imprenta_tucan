from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_roles, name='lista_roles'),
    path('alta/', views.alta_rol, name='alta_rol'),
    path('modificar/<int:idRol>/', views.modificar_rol, name='modificar_rol'),
    path('eliminar/<int:idRol>/', views.eliminar_rol, name='eliminar_rol'),
    path('desactivar/<int:idRol>/', views.desactivar_rol, name='desactivar_rol'),
    path('reactivar/<int:idRol>/', views.reactivar_rol, name='reactivar_rol'),


]
