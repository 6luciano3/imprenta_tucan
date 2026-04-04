from django.db import migrations, models
import proveedores.models


class Migration(migrations.Migration):

    dependencies = [
        ('proveedores', '0014_alter_proveedor_email_unique_alter_proveedor_rubro_blank'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proveedor',
            name='cuit',
            field=models.CharField(
                blank=True, max_length=13, null=True, unique=True,
                validators=[proveedores.models.validar_cuit]
            ),
        ),
        migrations.AlterField(
            model_name='proveedor',
            name='direccion',
            field=models.TextField(blank=True),
        ),
    ]
