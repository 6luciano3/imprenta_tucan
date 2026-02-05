from django.urls import path
from . import views

urlpatterns = [
    path('', views.panel, name='automatizacion_panel'),
    path('ordenes/', views.lista_ordenes, name='automatizacion_ordenes'),
    path('ofertas/', views.lista_ofertas, name='automatizacion_ofertas'),
    path('demo/', views.generar_demo, name='automatizacion_demo'),
]
