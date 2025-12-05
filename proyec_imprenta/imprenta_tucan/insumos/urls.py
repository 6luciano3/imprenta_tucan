from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_insumos, name='lista_insumos'),
    path('crear/', views.crear_insumo, name='crear_insumo'),
    path('alta/', views.alta_insumo, name='alta_insumo'),
    path('buscar/', views.buscar_insumo, name='buscar_insumo'),
    path('seleccionar/<int:pk>/', views.seleccionar_insumo, name='seleccionar_insumo'),
    path('modificar/<int:idInsumo>/', views.modificar_insumo, name='modificar_insumo'),
    path('baja/<int:idInsumo>/', views.baja_insumo, name='baja_insumo'),
    path('activar/<int:idInsumo>/', views.activar_insumo, name='activar_insumo'),
    path('eliminar/<int:idInsumo>/', views.eliminar_insumo, name='eliminar_insumo'),
    path('<int:pk>/', views.detalle_insumo, name='detalle_insumo'),
    path('<int:pk>/editar/', views.editar_insumo, name='editar_insumo'),
    path('lista_proyecciones/', views.lista_proyecciones, name='lista_proyecciones'),
    path('validar_proyeccion/<int:pk>/', views.validar_proyeccion, name='validar_proyeccion'),
]
