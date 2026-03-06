from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insumos', '0008_stock_minimo_manual'),
    ]

    operations = [
        migrations.AddField(
            model_name='insumo',
            name='cantidad_compra_sugerida',
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text='Cantidad estándar a reponer cuando se detecta necesidad de compra. Reemplaza el dict hardcodeado en tasks.',
            ),
        ),
    ]
