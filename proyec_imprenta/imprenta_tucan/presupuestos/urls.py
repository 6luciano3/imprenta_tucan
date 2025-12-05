from django.urls import path
from . import views

app_name = 'presupuestos'

urlpatterns = [
    path('crear/', views.crear_presupuesto, name='crear'),
    path('lista/', views.lista_presupuestos, name='lista'),
    path('editar/<int:pk>/', views.editar_presupuesto, name='editar'),
    path('eliminar/<int:pk>/', views.eliminar_presupuesto, name='eliminar'),
]
