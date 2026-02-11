from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = "Muestra el estado del backend de email y credenciales AWS (STS)"

    def handle(self, *args, **options):
        backend = getattr(settings, 'EMAIL_BACKEND', 'N/A')
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@imprenta.local')
        provider = getattr(settings, 'ANYMAIL_PROVIDER', '') if hasattr(settings, 'ANYMAIL_PROVIDER') else ''
        region = getattr(settings, 'AWS_REGION', 'N/A') if hasattr(settings, 'AWS_REGION') else 'N/A'

        self.stdout.write(self.style.WARNING(f"EMAIL_BACKEND: {backend}"))
        self.stdout.write(self.style.WARNING(f"ANYMAIL_PROVIDER: {provider}"))
        self.stdout.write(self.style.WARNING(f"DEFAULT_FROM_EMAIL: {from_email}"))
        self.stdout.write(self.style.WARNING(f"AWS_REGION: {region}"))

        try:
            import boto3
            sts = boto3.client('sts')
            ident = sts.get_caller_identity()
            arn = ident.get('Arn', 'N/A')
            self.stdout.write(self.style.SUCCESS(f"✅ Credenciales activas: {arn}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ No se detectaron credenciales AWS válidas: {e}"))
            self.stdout.write("Sugerencias:")
            self.stdout.write("- Ejecuta: aws sso login --profile <tu-perfil>")
            self.stdout.write("- Exporta: $env:AWS_PROFILE y $env:AWS_REGION")
