from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0013_add_pago_factura'),
    ]

    operations = [
        migrations.AddField(
            model_name='factura',
            name='anulada',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='factura',
            name='fecha_anulacion',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='factura',
            name='motivo_anulacion',
            field=models.TextField(blank=True),
        ),
    ]
