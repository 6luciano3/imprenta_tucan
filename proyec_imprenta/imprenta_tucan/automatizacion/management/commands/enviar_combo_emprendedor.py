from django.core.management.base import BaseCommand
from clientes.models import Cliente
from automatizacion.models import OfertaPropuesta, MensajeOferta
from automatizacion.services import enviar_oferta_email
from django.utils import timezone
from django.conf import settings

class Command(BaseCommand):
    help = 'Envía la oferta Combo Emprendedor a todos los clientes activos con email.'

    def handle(self, *args, **options):
        clientes = Cliente.objects.filter(estado='Activo').exclude(email__isnull=True).exclude(email='')
        total = clientes.count()
        self.stdout.write(f"Encontrados {total} clientes activos con email.")
        enviados = 0
        for cliente in clientes:
            oferta = OfertaPropuesta.objects.create(
                cliente=cliente,
                titulo='Combo Emprendedor',
                descripcion='Oferta especial para emprendedores: tarjetas personales, volantes, banner, sello automático. Subtotal $180.500, descuento 10%, total final $162.450.',
                tipo='descuento',
                parametros={'descuento': 10, 'productos': [
                    {'nombre': 'Tarjetas personales full color', 'cantidad': 500, 'precio_unitario': 45, 'subtotal': 22500},
                    {'nombre': 'Volantes A5 color frente', 'cantidad': 1000, 'precio_unitario': 35, 'subtotal': 35000},
                    {'nombre': 'Banner 80x200 con estructura', 'cantidad': 1, 'precio_unitario': 95000, 'subtotal': 95000},
                    {'nombre': 'Sello automático', 'cantidad': 1, 'precio_unitario': 28000, 'subtotal': 28000},
                ], 'subtotal': 180500, 'total_final': 162450},
                score_al_generar=0,
                estado='enviada',
                administrador=None,
                fecha_validacion=timezone.now(),
            )
            ok, err = enviar_oferta_email(oferta)
            MensajeOferta.objects.create(
                oferta=oferta,
                cliente=cliente,
                estado='enviado' if ok else 'fallido',
                canal='email',
                detalle='Combo Emprendedor enviado automáticamente.' if ok else f'Error: {err}',
            )
            enviados += 1 if ok else 0
            self.stdout.write(f"{'✅' if ok else '❌'} {cliente.email}: {'Enviado' if ok else err}")
        self.stdout.write(f"\nTotal enviados correctamente: {enviados} de {total}")
