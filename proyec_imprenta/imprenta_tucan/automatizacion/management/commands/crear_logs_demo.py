from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from utils.automationlog_utils import registrar_automation_log


class Command(BaseCommand):
    help = 'Genera eventos de AutomationLog de demostración para validar el panel y la API.'

    def handle(self, *args, **options):
        User = get_user_model()
        usuario = User.objects.filter(is_superuser=True).first()

        registrar_automation_log(
            'DEMO_RANKING',
            'Se ejecutó ranking de clientes (demo).',
            usuario=usuario,
            datos={'source': 'demo', 'modulo': 'ranking_clientes'}
        )

        registrar_automation_log(
            'DEMO_OFERTAS',
            'Se generaron ofertas automáticas (demo).',
            usuario=usuario,
            datos={'source': 'demo', 'modulo': 'ofertas_automaticas', 'count': 2}
        )

        registrar_automation_log(
            'DEMO_APROBACION',
            'Se aprobó automáticamente un pedido (demo).',
            usuario=usuario,
            datos={'source': 'demo', 'modulo': 'aprobaciones', 'pedido_id': 0, 'aprobado': True}
        )

        self.stdout.write(self.style.SUCCESS('Se crearon 3 logs de automatización de demo.'))
