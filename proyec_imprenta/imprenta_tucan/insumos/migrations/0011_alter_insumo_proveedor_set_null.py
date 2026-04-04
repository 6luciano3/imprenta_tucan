from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('insumos', '0010_add_sc_models'),
        ('proveedores', '0015_alter_proveedor_cuit_null_alter_proveedor_direccion_blank'),
    ]

    operations = [
        migrations.AlterField(
            model_name='insumo',
            name='proveedor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='insumos',
                to='proveedores.proveedor',
            ),
        ),
    ]
