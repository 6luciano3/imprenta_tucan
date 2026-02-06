# productos/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('lista/', views.lista_productos, name='lista_productos'),
    path('crear/', views.crear_producto, name='crear_producto'),
    # Alias para cumplir nombres solicitados
    path('alta/', views.crear_producto, name='alta_producto'),
    # CRUD de Catálogo desde Alta (categorías, tipos, unidades)
    path('alta/categorias/', views.lista_categorias, name='lista_categorias'),
    path('alta/categorias/crear/', views.crear_categoria, name='crear_categoria'),
    path('alta/categorias/editar/<int:pk>/', views.editar_categoria, name='editar_categoria'),
    path('alta/categorias/eliminar/<int:pk>/', views.eliminar_categoria, name='eliminar_categoria'),

    path('alta/tipos/', views.lista_tipos, name='lista_tipos'),
    path('alta/tipos/crear/', views.crear_tipo, name='crear_tipo'),
    path('alta/tipos/editar/<int:pk>/', views.editar_tipo, name='editar_tipo'),
    path('alta/tipos/eliminar/<int:pk>/', views.eliminar_tipo, name='eliminar_tipo'),

    path('alta/unidades/', views.lista_unidades, name='lista_unidades'),
    path('alta/unidades/crear/', views.crear_unidad, name='crear_unidad'),
    path('alta/unidades/editar/<int:pk>/', views.editar_unidad, name='editar_unidad'),
    path('alta/unidades/eliminar/<int:pk>/', views.eliminar_unidad, name='eliminar_unidad'),
    path('editar/<int:idProducto>/', views.editar_producto, name='editar_producto'),
    path('modificar/<int:idProducto>/', views.editar_producto, name='modificar_producto'),
    path('activar/<int:idProducto>/', views.activar_producto, name='activar_producto'),
    path('eliminar/<int:idProducto>/', views.eliminar_producto, name='eliminar_producto'),
    path('detalle/<int:idProducto>/', views.detalle_producto, name='detalle_producto'),
    path('calcular-consumo/<int:producto_id>/<int:cantidad>/', views.calcular_consumo, name='calcular_consumo_producto'),
    path('receta-insumos/<int:producto_id>/', views.receta_insumos, name='receta_insumos_producto'),
]
