from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('clientes', '0006_alter_cliente_ciudad'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cliente',
            name='razon_social',
            field=models.CharField(max_length=150, blank=True, null=True, db_column='razónSocial'),
        ),
        migrations.AlterField(
            model_name='cliente',
            name='direccion',
            field=models.CharField(max_length=200, db_column='dirección'),
        ),
        migrations.AlterField(
            model_name='cliente',
            name='estado',
            field=models.CharField(max_length=10, choices=[('Activo', 'Activo'), ('Inactivo', 'Inactivo')], default='Activo', db_column='estadoCliente'),
        ),
    ]
