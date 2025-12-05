from django.contrib.messages import constants as messages
from pathlib import Path
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent.parent / '.env')


# Seguridad y entorno
SECRET_KEY = os.environ.get('SECRET_KEY', 'clave-insegura')
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')

# Aplicaciones instaladas
INSTALLED_APPS = [
    # Apps del sistema
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Apps del proyecto
    'clientes',
    'pedidos',
    'productos',
    'proveedores',
    'insumos',
    'presupuestos',
    'usuarios',
    'roles',
    'permisos',
    'widget_tweaks',
    'estadisticas',
    'auditoria',
    'configuracion',
    'geo',
    'automatizacion',
    'rest_framework',
]

# Modelo de usuario personalizado
AUTH_USER_MODEL = 'usuarios.Usuario'

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'auditoria.middleware.AuditMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Configuración de URLs
ROOT_URLCONF = 'impre_tucan.urls'
WSGI_APPLICATION = 'impre_tucan.wsgi.application'

# Plantillas
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'configuracion.context_processors.module_visibility',
            ],
        },
    },
]

# Base de datos
DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': os.environ.get('DB_NAME', BASE_DIR / 'db.sqlite3'),
    }
}

# Internacionalización
LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Archivos estáticos
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Archivos media
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Seguridad para producción
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
# Política estricta por defecto: NO permitir iframes
# Permitir embebido interno de listados en iframes (modal gestión) usando SAMEORIGIN
X_FRAME_OPTIONS = 'SAMEORIGIN'

# WhiteNoise para servir archivos estáticos en producción
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Redirecciones de login/logout
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
LOGIN_URL = '/accounts/login/'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


MESSAGE_TAGS = {
    messages.DEBUG: 'debug',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'error',
}

# Configuración Celery
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_BEAT_SCHEDULE = {}

from .celery import app as celery_app
__all__ = ('celery_app',)
