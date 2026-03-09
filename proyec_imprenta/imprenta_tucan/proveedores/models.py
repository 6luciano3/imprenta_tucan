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
        parsed = phonenumbers.parse(valor, None)
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


class Rubro(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Proveedor(models.Model):
    nombre = models.CharField(max_length=100, db_column='nombreProveedor')
    apellido = models.CharField(max_length=100, default='Ejemplo')
    cuit = models.CharField(max_length=13, unique=True)  # Formato: XX-XXXXXXXX-X
    email = models.EmailField()
    telefono = models.CharField(max_length=20, blank=True)
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
    direccion = models.TextField()
    # Campo nuevo para normalizar rubro como catálogo
    rubro_fk = models.ForeignKey('proveedores.Rubro', on_delete=models.PROTECT, null=True, blank=True, related_name='proveedores')
    # Campo textual legado para compatibilidad; puede eliminarse luego de migrar formularios/vistas
    rubro = models.CharField(max_length=50)

    # URL de API para consulta de stock en proveedor real
    api_stock_url = models.URLField(blank=True, null=True, help_text="Endpoint para consulta de stock en proveedor real")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        # Mostrar nombre y CUIT si está disponible
        return f"{self.nombre}{f' ({self.cuit})' if self.cuit else ''}"

    @property
    def numero_whatsapp(self) -> str | None:
        """Retorna el número de WhatsApp a usar: `whatsapp` si está definido, si no `telefono_e164`."""
        return self.whatsapp or self.telefono_e164

    @property
    def rubro_nombre(self):
        return (self.rubro_fk.nombre if self.rubro_fk else None) or (self.rubro or None)


# Modelo para parametrización de proveedores
class ProveedorParametro(models.Model):
    clave = models.CharField(max_length=50, unique=True)
    valor = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.clave}: {self.valor}"
