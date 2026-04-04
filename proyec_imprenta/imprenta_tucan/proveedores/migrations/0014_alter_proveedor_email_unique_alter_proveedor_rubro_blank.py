from django.db import migrations, models
import proveedores.models


class Migration(migrations.Migration):

    dependencies = [
        ('proveedores', '0013_alter_proveedor_telefono'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proveedor',
            name='email',
            field=models.EmailField(max_length=254, unique=True),
        ),
        migrations.AlterField(
            model_name='proveedor',
            name='rubro',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AlterField(
            model_name='proveedor',
            name='cuit',
            field=models.CharField(max_length=13, unique=True, validators=[proveedores.models.validar_cuit]),
        ),
    ]
