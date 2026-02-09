from django.urls import path
from . import views

urlpatterns = [
    path('lista/', views.lista_auditoria, name='lista_auditoria'),
    path('ver/<int:pk>/', views.ver_auditoria, name='ver_auditoria'),
    path('eliminar/<int:pk>/', views.eliminar_auditoria, name='eliminar_auditoria'),
    path('exportar-csv/', views.exportar_auditoria_csv, name='exportar_auditoria_csv'),
    path('exportar-xlsx/', views.exportar_auditoria_xlsx, name='exportar_auditoria_xlsx'),
]
