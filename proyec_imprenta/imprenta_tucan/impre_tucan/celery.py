import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')

app = Celery('impre_tucan')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
