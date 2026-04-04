from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compras', '0007_remito_numero_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='detalleremito',
            name='precio_unitario',
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=10,
                help_text='Precio al que se recibió el insumo en este remito',
            ),
        ),
    ]
