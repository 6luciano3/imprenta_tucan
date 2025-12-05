from django.urls import path
from . import views

urlpatterns = [
    # Autenticación
    path('login/', views.iniciar_sesion, name='login'),
    path('logout/', views.cerrar_sesion, name='logout'),

    # Gestión de usuarios
    path('lista/', views.lista_usuarios, name='lista_usuarios'),
    path('buscar/', views.buscar_usuario, name='buscar_usuario'),  # alias de lista con filtro
    path('alta/', views.alta_usuario, name='alta_usuario'),
    path('modificar/<int:idUsuario>/', views.modificar_usuario, name='modificar_usuario'),
    path('detalle/<int:idUsuario>/', views.detalle_usuario, name='detalle_usuario'),
    path('baja/<int:idUsuario>/', views.baja_usuario, name='baja_usuario'),
    path('reactivar/<int:idUsuario>/', views.reactivar_usuario, name='reactivar_usuario'),

    # Eliminar dashboard duplicado para evitar confusión

    # Dashboard principal
    path('dashboard/', views.dashboard, name='dashboard'),
]
