from django.urls import path
from . import views

app_name = 'estadisticas'

urlpatterns = [
    path('', views.dashboard_estadisticas, name='dashboard'),
    path('api/pedidos-por-estado/', views.api_pedidos_por_estado, name='api_pedidos_por_estado'),
    path('api/ingresos-por-mes/', views.api_ingresos_por_mes, name='api_ingresos_por_mes'),
    path('api/top-productos/', views.api_top_productos, name='api_top_productos'),
    path('api/kpis/', views.api_kpis, name='api_kpis'),
]
