import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','impre_tucan.settings')
django.setup()
from auditoria.models import AuditEntry
from django.utils import timezone
from django.template import engines

entry = AuditEntry.objects.order_by('-timestamp').first()
if entry:
    t = entry.timestamp
    tpl = engines['django'].from_string("{{ ts|date:'d/m/Y H:i:s' }}")
    rendered = tpl.render({'ts': t})
    local = timezone.localtime(t)
    print('UTC guardado:   ', t.strftime('%d/%m/%Y %H:%M:%S'), '(UTC)')
    print('Hora Argentina: ', local.strftime('%d/%m/%Y %H:%M:%S'), '(UTC-3)')
    print('Template render:', rendered.strip())
    ok = rendered.strip() == local.strftime('%d/%m/%Y %H:%M:%S')
    print('Correcto:       ', ok)
else:
    print('No hay entradas de auditoria')
