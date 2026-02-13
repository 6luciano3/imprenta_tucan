
from django.contrib.messages import constants as messages
from pathlib import Path
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent.parent / '.env')


# =====================

# CRITICAL PATH/EMAIL/STATIC/MEDIA VARIABLES (must be defined before use)
# =====================
# BASE_DIR already defined above
STATIC_URL = '/static/'
STATICFILES_DIRS = [str(BASE_DIR / 'static')]
STATIC_ROOT = str(BASE_DIR / 'staticfiles')
MEDIA_URL = '/media/'
MEDIA_ROOT = str(BASE_DIR / 'media')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'no-reply@imprenta.local')
EMAIL_FILE_PATH = os.environ.get('EMAIL_FILE_PATH', str(BASE_DIR / 'sent_emails'))
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1').strip()


# Debug prints
print("[DEBUG settings.py] BASE_DIR:", BASE_DIR)
print("[DEBUG settings.py] STATICFILES_DIRS:", STATICFILES_DIRS)
print("[DEBUG settings.py] STATIC_ROOT:", STATIC_ROOT)
print("[DEBUG settings.py] MEDIA_ROOT:", MEDIA_ROOT)
print("[DEBUG settings.py] EMAIL_FILE_PATH:", EMAIL_FILE_PATH)
print("[DEBUG settings.py] DEFAULT_FROM_EMAIL:", DEFAULT_FROM_EMAIL)
print("[DEBUG settings.py] AWS_REGION:", AWS_REGION)



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
    'dashboard',
    'rest_framework',
    'anymail',
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
        'DIRS': [str(BASE_DIR / 'templates')],
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

# Prints de depuración después del cierre del bloque TEMPLATES
print("[DEBUG settings.py] TEMPLATES:", TEMPLATES)

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': str(BASE_DIR / 'db.sqlite3'),
    }
}
print("[DEBUG settings.py] DATABASES:", DATABASES)

# Internacionalización
LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_L10N = True
USE_TZ = True



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
CELERY_BEAT_SCHEDULE = {
    'prediccion-demanda-cada-hora': {
        'task': 'automatizacion.tasks.tarea_prediccion_demanda',
        'schedule': 60 * 60,
    },
    'anticipacion-compras-cada-2-horas': {
        'task': 'automatizacion.tasks.tarea_anticipacion_compras',
        'schedule': 2 * 60 * 60,
    },
    'ranking-clientes-cada-hora': {
        'task': 'automatizacion.tasks.tarea_ranking_clientes',
        'schedule': 60 * 60,
    },
    'scores-proveedores-cada-6-horas': {
        'task': 'automatizacion.tasks.tarea_recalcular_scores_proveedores',
        'schedule': 6 * 60 * 60,
    },
    'generar-ofertas-diario': {
        'task': 'automatizacion.tasks.tarea_generar_ofertas',
        'schedule': 24 * 60 * 60,
    },
    'alertas-retraso-cada-30min': {
        'task': 'automatizacion.tasks.tarea_alertas_retraso',
        'schedule': 30 * 60,
    },
    'presupuestos-ponderados-cada-30min': {
        'task': 'automatizacion.tasks.tarea_automatizacion_presupuestos_ponderada',
        'schedule': 30 * 60,
    },
    'proyecciones-insumos-diario': {
        'task': 'insumos.tasks.generar_proyecciones_insumos',
        'schedule': 24 * 60 * 60,  # cada 24 horas
    },
}

from .celery import app as celery_app
__all__ = ('celery_app',)


# Anymail (SES exclusivo) vía API/SSO/IAM
# Se fuerza el uso de Amazon SES sin permitir SendGrid/Mailgun.
ANYMAIL_PROVIDER = 'ses'

# Backend de email: SES únicamente

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = '6luciano10@gmail.com'
EMAIL_HOST_PASSWORD = 'hpmybzczlzuksshb'  # Contraseña de aplicación de Google para envío real


# Configuración Anymail para SES. Las credenciales provienen de AWS SSO/IAM (boto3).
ANYMAIL = {
    'AMAZON_SES_CLIENT_PARAMS': {
        'region_name': AWS_REGION,
    }
}
