from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0003_notificacion'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usuario',
            name='nombre',
            field=models.CharField(max_length=100, db_column='nombreUsuario', verbose_name='Nombre'),
        ),
    ]
