# Detectar entorno de test
import sys
TESTING = 'test' in sys.argv

from django.contrib.messages import constants as messages
from pathlib import Path
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent.parent / '.env')

# Agregar proyec_imprenta/ al path para que el módulo core/ sea importable
if str(BASE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(BASE_DIR.parent))


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



# Seguridad y entorno
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')

# SECRET_KEY: falla ruidosamente en producción si no está definida en el entorno.
if not DEBUG:
    SECRET_KEY = os.environ['SECRET_KEY']  # KeyError en producción si falta
else:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-no-usar-en-produccion')

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
    'reportes',
    'api',
    # 'anymail',  # desactivado - usando Gmail SMTP directo
]

# Modelo de usuario personalizado
AUTH_USER_MODEL = 'usuarios.Usuario'

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
                    'configuracion.context_processors.empresa_context',
            ],
        },
    },
]

# Prints de depuración después del cierre del bloque TEMPLATES


db_name_env = os.environ.get('DB_NAME')
db_name = db_name_env if db_name_env else str(BASE_DIR / 'db.sqlite3')
DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': db_name,
    }
}


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
    'ranking-clientes-diario': {
        'task': 'automatizacion.tasks.tarea_ranking_clientes',
        'schedule': 24 * 60 * 60,
    },
    'scores-proveedores-cada-6-horas': {
        'task': 'automatizacion.tasks.tarea_recalcular_scores_proveedores',
        'schedule': 6 * 60 * 60,
    },
    'verificar-generacion-ofertas-cada-hora': {
        'task': 'automatizacion.tasks.tarea_verificar_generacion_ofertas',
        'schedule': 60 * 60,
    },
    'expirar-ofertas-diario': {
        'task': 'automatizacion.tasks.tarea_expirar_ofertas',
        'schedule': 24 * 60 * 60,  # cada día a las 2 AM (ajustable con crontab)
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

# Backend de email: SMTP si hay contraseña configurada, filebased en local/dev
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', '6luciano10@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

# Token secreto para autenticar webhooks internos (callbacks de automatización).
# Setear en producción vía variable de entorno AUTOMATION_WEBHOOK_SECRET.
AUTOMATION_WEBHOOK_SECRET = os.environ.get('AUTOMATION_WEBHOOK_SECRET', '')

if EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND  = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST     = 'smtp.gmail.com'
    EMAIL_PORT     = 587
    EMAIL_USE_TLS  = True
else:
    # Sin contraseña SMTP → escribe los emails como archivos en sent_emails/
    EMAIL_BACKEND  = 'django.core.mail.backends.filebased.EmailBackend'


# Configuración Anymail para SES. Las credenciales provienen de AWS SSO/IAM (boto3).
ANYMAIL = {
    'AMAZON_SES_CLIENT_PARAMS': {
        'region_name': AWS_REGION,
    }
}
