# Línea eliminada: estaba fuera de lugar y ya está incluida correctamente abajo
from django.urls import path
from . import views
from .views_api import formula_validate_api
from .views_parametros import parametros_automatizacion

urlpatterns = [
    path('empresa/', views.empresa_config, name='empresa_config'),
    path('', views.configuracion_home, name='configuracion_home'),
    path('motor-demanda/', views.motor_demanda_config, name='motor_demanda_config'),
    path('proyeccion-demanda/', views.proyeccion_demanda_config, name='proyeccion_demanda_config'),
    path('ofertas/reglas/', views.editar_reglas_ofertas, name='editar_reglas_ofertas'),
    path('ofertas/segmentadas/', views.ofertas_segmentadas_config, name='ofertas_segmentadas_config'),
    path('ofertas/', views.ofertas_hub, name='ofertas_hub'),
    path('ofertas/general/', views.ofertas_general_config, name='ofertas_general_config'),
    path('unidades/', views.unidad_list, name='unidad_list'),
    path('unidades/nueva/', views.unidad_create, name='unidad_create'),
    path('unidades/<int:pk>/editar/', views.unidad_update, name='unidad_update'),
    path('formulas/', views.lista_formulas, name='lista_formulas'),
    path('formulas/nueva/', views.crear_formula, name='crear_formula'),
    path('formulas/<int:pk>/editar/', views.editar_formula, name='editar_formula'),
    path('formulas/<int:pk>/desactivar/', views.desactivar_formula, name='desactivar_formula'),
    path('formulas/<int:pk>/activar/', views.activar_formula, name='activar_formula'),
    path('api/configuracion/formula/validate/', formula_validate_api, name='validar_formula'),
    path('recetas/', views.receta_producto_list, name='receta_producto_list'),
    path('recetas/nueva/', views.receta_producto_create, name='receta_producto_create'),
    path('recetas/<int:pk>/editar/', views.receta_producto_update, name='receta_producto_update'),
    path('recetas/<int:pk>/eliminar/', views.receta_producto_delete, name='receta_producto_delete'),
    path('recetas/<int:pk>/editar_formula/', views.receta_producto_update_formula, name='receta_producto_update_formula'),
    path('parametros/', parametros_automatizacion, name='parametros_automatizacion'),
    path('automatizacion-compras/', views.automatizacion_compras_config, name='automatizacion_compras_config'),
]