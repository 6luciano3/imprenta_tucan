from django.urls import path
from . import views

urlpatterns = [
    path('', views.panel, name='automatizacion_panel'),
    path('ordenes/', views.lista_ordenes, name='automatizacion_ordenes'),
    path('ofertas/', views.lista_ofertas, name='automatizacion_ofertas'),
    path('ranking/', views.lista_ranking_clientes, name='ranking_clientes'),
    # Gestión de ofertas propuestas (admin)
    path('propuestas/', views.ofertas_propuestas_admin, name='ofertas_propuestas'),
    path('propuestas/<int:oferta_id>/aprobar/', views.aprobar_oferta, name='aprobar_oferta'),
    path('propuestas/<int:oferta_id>/rechazar/', views.rechazar_oferta, name='rechazar_oferta'),
    path('propuestas/generar/', views.generar_propuestas, name='generar_propuestas'),
    # Ofertas para cliente
    path('mis-ofertas/', views.mis_ofertas_cliente, name='mis_ofertas_cliente'),
    path('mis-ofertas/<int:oferta_id>/confirmar/', views.confirmar_oferta_cliente, name='confirmar_oferta_cliente'),
    path('mis-ofertas/<int:oferta_id>/rechazar/', views.rechazar_oferta_cliente, name='rechazar_oferta_cliente'),
    path('demo/', views.generar_demo, name='automatizacion_demo'),
]
