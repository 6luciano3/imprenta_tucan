from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insumos', '0013_add_stock_minimo_calculado'),
    ]

    operations = [
        migrations.AddField(
            model_name='proyeccioninsumo',
            name='fuente',
            field=models.CharField(
                blank=True,
                choices=[
                    ('media_movil', 'Media Móvil Ponderada'),
                    ('ets', 'Suavizado Exponencial (ETS)'),
                    ('stock_minimo', 'Stock Mínimo Sugerido'),
                    ('fallback', 'Valor por defecto'),
                ],
                default='media_movil',
                help_text='Origen del valor proyectado: algoritmo usado o fallback aplicado.',
                max_length=20,
            ),
        ),
    ]
