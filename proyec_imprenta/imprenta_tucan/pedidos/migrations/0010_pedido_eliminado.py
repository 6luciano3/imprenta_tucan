from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0009_ordencompra_fecha_respuesta'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedido',
            name='eliminado',
            field=models.BooleanField(
                default=False,
                help_text='Baja lógica — el registro no se borra físicamente',
            ),
        ),
    ]
