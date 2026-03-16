import phonenumbers
from django.core.exceptions import ValidationError
from django.db import models


def validar_telefono_e164(valor):
    """
    Valida que el número esté en formato E.164 (+<código de país><número>).
    Ejemplo válido: +5493816123456
    """
    if not valor:
        return  # campo opcional
    try:
        parsed = phonenumbers.parse(valor, None)  # None obliga a incluir código de país
    except phonenumbers.NumberParseException as exc:
        raise ValidationError(
            f'Número de teléfono inválido: {exc}. '
            'Formato requerido: +<cód. país><número>, ej: +5493816123456'
        )
    if not phonenumbers.is_valid_number(parsed):
        raise ValidationError(
            f'El número {valor!r} no es válido para ningún país. '
            'Ejemplo: +5493816123456'
        )




ESTADOS_BLOQUEANTES = {"Pendiente", "En Proceso", "Completado"}
class Cliente(models.Model):
    TIPO_CLIENTE_CHOICES = [
        ("premium", "Premium"),
        ("estrategico", "Estratégico"),
        ("estandar", "Estándar"),
        ("nuevo", "Nuevo"),
    ]

    nombre = models.CharField(max_length=100)
    tipo_cliente = models.CharField(
        max_length=15,
        choices=TIPO_CLIENTE_CHOICES,
        default="nuevo",
        verbose_name="Tipo de Cliente"
    )
    apellido = models.CharField(max_length=100)
    razon_social = models.CharField(max_length=150, blank=True, null=True, db_column='razónSocial')
    cuit = models.CharField(max_length=11, blank=False, null=False, unique=True, verbose_name="CUIT", default="00000000000")
    direccion = models.CharField(max_length=200, db_column='dirección')
    ciudad = models.CharField(max_length=100, default='Posadas')
    provincia = models.CharField(max_length=100, default='Misiones')
    pais = models.CharField(max_length=100, default='Argentina')
    telefono = models.CharField(max_length=20, blank=True, null=True)
    celular = models.CharField(max_length=20, blank=True, null=True)
    telefono_e164 = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        validators=[validar_telefono_e164],
        verbose_name='Teléfono (E.164)',
        help_text='Número celular en formato internacional, ej: +5493816123456. '
                  'Necesario para enviar SMS y WhatsApp.',
    )
    whatsapp = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        validators=[validar_telefono_e164],
        verbose_name='WhatsApp',
        help_text='Número de WhatsApp en formato E.164. '
                  'Dejar en blanco si coincide con Teléfono (E.164).',
    )
    email = models.EmailField(unique=True)
    email_verificado = models.BooleanField(default=False, help_text='Indica si el email del cliente fue verificado y es valido para envios')
    estado = models.CharField(max_length=10, choices=[('Activo', 'Activo'), ('Inactivo', 'Inactivo')], default='Activo', db_column='estadoCliente')
    puntaje_estrategico = models.FloatField(default=0)
    fecha_ultima_actualizacion = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.razon_social or 'Sin razón social'})"

    @property
    def numero_whatsapp(self) -> str | None:
        """Retorna el número de WhatsApp a usar: `whatsapp` si está definido, si no `telefono_e164`."""
        return self.whatsapp or self.telefono_e164

    def puede_eliminarse(self):
        return not self.pedido_set.filter(estado__nombre__in=ESTADOS_BLOQUEANTES).exists()

    def pedidos_bloqueantes(self):
        return self.pedido_set.filter(estado__nombre__in=ESTADOS_BLOQUEANTES)

