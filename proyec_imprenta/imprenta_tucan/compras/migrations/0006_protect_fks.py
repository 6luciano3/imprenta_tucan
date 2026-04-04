from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('compras', '0005_agregar_campos_envio'),
        ('proveedores', '0015_alter_proveedor_cuit_null_alter_proveedor_direccion_blank'),
        ('insumos', '0012_remove_insumo_precio'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ordencompra',
            name='proveedor',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='ordenes_compra_app',
                to='proveedores.proveedor',
            ),
        ),
        migrations.AlterField(
            model_name='detalleordencompra',
            name='insumo',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='detalles_orden_compra',
                to='insumos.insumo',
            ),
        ),
        migrations.AlterField(
            model_name='remito',
            name='proveedor',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='remitos_compras',
                to='proveedores.proveedor',
            ),
        ),
        migrations.AlterField(
            model_name='detalleremito',
            name='insumo',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='detalles_remito_compras',
                to='insumos.insumo',
            ),
        ),
    ]
