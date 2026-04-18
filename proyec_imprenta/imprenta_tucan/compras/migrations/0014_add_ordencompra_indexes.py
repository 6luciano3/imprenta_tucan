from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compras', '0013_comprapropuesta_borrador_oc_to_compras'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='ordencompra',
            index=models.Index(fields=['estado', 'fecha_creacion'], name='compra_estado_fecha_idx'),
        ),
        migrations.AddIndex(
            model_name='ordencompra',
            index=models.Index(fields=['proveedor', 'estado'], name='compra_proveedor_estado_idx'),
        ),
    ]
