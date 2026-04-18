from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0014_factura_anulacion'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='pedido',
            index=models.Index(fields=['estado', 'fecha_pedido'], name='pedido_estado_fecha_idx'),
        ),
        migrations.AddIndex(
            model_name='pedido',
            index=models.Index(fields=['cliente', 'estado'], name='pedido_cliente_estado_idx'),
        ),
    ]
