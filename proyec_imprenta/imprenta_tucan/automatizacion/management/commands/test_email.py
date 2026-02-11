from django.core.management.base import BaseCommand
from django.core.mail import send_mail
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
            sent = send_mail(subject, body, from_email, [to], fail_silently=False)
            if sent:
                self.stdout.write(self.style.SUCCESS('OK: Email enviado (o impreso en consola si console backend).'))
            else:
                self.stdout.write(self.style.ERROR('No se pudo enviar el email (send_mail retornó 0).'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al enviar: {e}'))
