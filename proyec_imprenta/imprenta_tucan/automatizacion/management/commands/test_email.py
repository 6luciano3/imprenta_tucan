from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Envía un email de prueba usando la configuración actual (EMAIL_BACKEND/SMTP)."

    def add_arguments(self, parser):
        parser.add_argument('--to', required=True, help='Dirección de email destino')
        parser.add_argument('--subject', default='Prueba Email Imprenta Tucán')
        parser.add_argument('--body', default='Este es un correo de prueba enviado por la aplicación.')

    def handle(self, *args, **options):
        to = options['to']
        subject = options['subject']
        body = options['body']
        backend = getattr(settings, 'EMAIL_BACKEND', 'N/A')
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@imprenta.local')
        self.stdout.write(self.style.WARNING(f"Usando EMAIL_BACKEND: {backend}"))
        self.stdout.write(self.style.WARNING(f"Desde: {from_email} → Hacia: {to}"))
        try:
            from core.notifications.engine import enviar_notificacion
            resultado = enviar_notificacion(
                destinatario=to,
                mensaje=body,
                canal='email',
                asunto=subject,
            )
            if resultado['ok']:
                self.stdout.write(self.style.SUCCESS('OK: Email enviado (o guardado si backend filebased).'))
            else:
                self.stdout.write(self.style.ERROR(f'No se pudo enviar el email: {resultado.get("error")}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al enviar: {e}'))
