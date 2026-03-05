"""Script de prueba: envia oferta a Luciano Adolfo Lopez ID=130."""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.utils import timezone
from clientes.models import Cliente
from automatizacion.models import OfertaPropuesta
from automatizacion.services import enviar_oferta_email

# Buscar cliente
try:
    cliente = Cliente.objects.get(pk=130)
    print(f"Cliente: {cliente.nombre} | email: {cliente.email}")
except Cliente.DoesNotExist:
    print("ERROR: Cliente ID=130 no encontrado")
    sys.exit(1)

if not cliente.email:
    print("ERROR: El cliente no tiene email")
    sys.exit(1)

# Crear nueva oferta con 20% de descuento
oferta = OfertaPropuesta.objects.create(
    cliente=cliente,
    titulo="Oferta Exclusiva - Marzo 2026",
    descripcion=(
        "Descuento exclusivo del 20 por ciento en tu proximo pedido. "
        "Aprovecha esta oportunidad preparada especialmente para vos."
    ),
    tipo="descuento",
    parametros={"descuento": 20},
    score_al_generar=79.51,
    estado="enviada",
    administrador=None,
    fecha_validacion=timezone.now(),
)
print(f"Oferta creada: ID={oferta.id} | token={oferta.token_email}")

# Enviar email real
ok, err = enviar_oferta_email(oferta)
if ok:
    print(f"=== EMAIL ENVIADO OK a {cliente.email} ===")
    print(f"Link aceptar : http://localhost:8000/automatizacion/oferta/{oferta.token_email}/aceptar/")
    print(f"Link rechazar: http://localhost:8000/automatizacion/oferta/{oferta.token_email}/rechazar/")
    print(f"Link ver     : http://localhost:8000/automatizacion/oferta/{oferta.token_email}/")
else:
    print(f"ERROR al enviar: {err}")
