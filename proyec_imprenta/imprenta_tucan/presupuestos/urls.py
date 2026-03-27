from django.urls import path
from . import views

app_name = 'presupuestos'

urlpatterns = [
    path('crear/', views.crear_presupuesto, name='crear'),
    path('lista/', views.lista_presupuestos, name='lista'),
    path('recordatorio/', views.recordatorio_presupuestos, name='recordatorio'),
    path('editar/<int:pk>/', views.editar_presupuesto, name='editar'),
    path('eliminar/<int:pk>/', views.eliminar_presupuesto, name='eliminar'),
    path('enviar/<int:pk>/', views.enviar_presupuesto, name='enviar'),
    path('respuesta/<uuid:token>/', views.respuesta_cliente_view, name='respuesta_cliente'),
    path('responder/<uuid:token>/<str:accion>/', views.procesar_respuesta, name='procesar_respuesta'),
    path('ok/<uuid:token>/<str:accion>/', views.accion_directa, name='accion_directa'),
    path('pdf/<uuid:token>/', views.descargar_pdf_presupuesto, name='pdf'),
    path('imagen/<uuid:token>/', views.imagen_presupuesto, name='imagen'),
]
