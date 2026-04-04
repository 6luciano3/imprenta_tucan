from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('insumos', '0011_alter_insumo_proveedor_set_null'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='insumo',
            name='precio',
        ),
    ]
