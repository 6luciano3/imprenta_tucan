import secrets
from django.db import migrations, models


def generar_tokens(apps, schema_editor):
    OrdenCompra = apps.get_model('compras', 'OrdenCompra')
    for oc in OrdenCompra.objects.filter(token_proveedor=''):
        oc.token_proveedor = secrets.token_urlsafe(32)
        oc.save(update_fields=['token_proveedor'])


class Migration(migrations.Migration):

    dependencies = [
        ('compras', '0010_orden_pago'),
    ]

    operations = [
        # Paso 1: agregar campo nullable sin unique
        migrations.AddField(
            model_name='ordencompra',
            name='token_proveedor',
            field=models.CharField(
                blank=True,
                max_length=64,
                default='',
                help_text='Token único enviado al proveedor para confirmar/rechazar sin login',
            ),
        ),
        # Paso 2: poblar tokens únicos en filas existentes
        migrations.RunPython(generar_tokens, migrations.RunPython.noop),
        # Paso 3: aplicar unique constraint
        migrations.AlterField(
            model_name='ordencompra',
            name='token_proveedor',
            field=models.CharField(
                blank=True,
                max_length=64,
                unique=True,
                default='',
                help_text='Token único enviado al proveedor para confirmar/rechazar sin login',
            ),
        ),
    ]
