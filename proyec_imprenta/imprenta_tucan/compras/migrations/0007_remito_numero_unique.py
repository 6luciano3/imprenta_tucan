from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compras', '0006_protect_fks'),
    ]

    operations = [
        migrations.AlterField(
            model_name='remito',
            name='numero',
            field=models.CharField(max_length=50, unique=True),
        ),
    ]
