from django.urls import path
from . import views


urlpatterns = [
    path('ciudades/', views.lista_ciudades, name='lista_ciudades'),
    path('ciudades/crear/', views.crear_ciudad, name='crear_ciudad'),
    path('ciudades/<int:id>/editar/', views.editar_ciudad, name='editar_ciudad'),
    path('ciudades/<int:id>/eliminar/', views.eliminar_ciudad, name='eliminar_ciudad'),
    path('ciudades/<int:id>/activar/', views.activar_ciudad, name='activar_ciudad'),
]
