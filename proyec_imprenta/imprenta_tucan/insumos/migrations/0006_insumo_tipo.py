from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insumos', '0005_insumo_descripcion'),
    ]

    operations = [
        migrations.AddField(
            model_name='insumo',
            name='tipo',
            field=models.CharField(
                choices=[('directo', 'Directo'), ('indirecto', 'Indirecto')],
                default='directo',
                help_text='Directo: se incorpora al producto. Indirecto: usado en el proceso pero no en el producto final.',
                max_length=10,
            ),
        ),
    ]
