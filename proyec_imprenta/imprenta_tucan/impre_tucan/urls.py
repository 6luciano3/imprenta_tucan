from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from impre_tucan.views import dashboard
from usuarios.views import inicio
from impre_tucan.views import confirmar_eliminacion_cliente
from . import views

urlpatterns = [
    # Administración
    path('admin/', admin.site.urls),
    path('', inicio, name='inicio'),

    # Autenticacion
    path('accounts/', include('django.contrib.auth.urls')),

    # Módulos del sistema
    path('clientes/', include('clientes.urls')),
    path('pedidos/', include('pedidos.urls')),
    path('productos/', include('productos.urls')),
    path('proveedores/', include('proveedores.urls')),
    path('insumos/', include('insumos.urls')),
    path('presupuestos/', include('presupuestos.urls')),
    path('usuarios/', include('usuarios.urls')),
    path('roles/', include('roles.urls')),
    path('permisos/', include('permisos.urls')),
    path('estadisticas/', include('estadisticas.urls')),
    path('geo/', include('geo.urls')),
    path('auditoria/', include('auditoria.urls')),
    path('configuracion/', include('configuracion.urls')),

    # Página principal
    path('dashboard/', dashboard, name='dashboard'),
    # Endpoints API Inteligente
    path('', include('api.urls')),
]

# Archivos multimedia en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
