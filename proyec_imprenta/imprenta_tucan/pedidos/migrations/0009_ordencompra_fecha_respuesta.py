from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0008_token_proveedor_orden_compra'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordencompra',
            name='fecha_respuesta',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Se asigna automáticamente la primera vez que el estado cambia a confirmada o rechazada.',
            ),
        ),
    ]
