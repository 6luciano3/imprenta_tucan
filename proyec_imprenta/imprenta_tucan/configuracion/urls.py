# Línea eliminada: estaba fuera de lugar y ya está incluida correctamente abajo
from django.urls import path
from . import views

urlpatterns = [
    path('', views.configuracion_home, name='configuracion_home'),
    path('unidades/', views.unidad_list, name='unidad_list'),
    path('unidades/nueva/', views.unidad_create, name='unidad_create'),
    path('unidades/<int:pk>/editar/', views.unidad_update, name='unidad_update'),
    path('formulas/', views.lista_formulas, name='lista_formulas'),
    path('formulas/nueva/', views.crear_formula, name='crear_formula'),
    path('formulas/<int:pk>/editar/', views.editar_formula, name='editar_formula'),
    path('formulas/<int:pk>/desactivar/', views.desactivar_formula, name='desactivar_formula'),
    path('formulas/<int:pk>/activar/', views.activar_formula, name='activar_formula'),
    path('api/configuracion/formula/validate/', views.validar_formula, name='validar_formula'),
    path('recetas/', views.receta_producto_list, name='receta_producto_list'),
    path('recetas/nueva/', views.receta_producto_create, name='receta_producto_create'),
    path('recetas/<int:pk>/editar/', views.receta_producto_update, name='receta_producto_update'),
    path('recetas/<int:pk>/eliminar/', views.receta_producto_delete, name='receta_producto_delete'),
    path('recetas/<int:pk>/editar_formula/', views.receta_producto_update_formula, name='receta_producto_update_formula'),
]
