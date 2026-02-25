from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0001_initial"),
    ]

    operations = [
        # Remove fields from Pedido
        migrations.RemoveField(
            model_name="pedido",
            name="producto",
        ),
        migrations.RemoveField(
            model_name="pedido",
            name="cantidad",
        ),
        migrations.RemoveField(
            model_name="pedido",
            name="especificaciones",
        ),
        # Create LineaPedido
        migrations.CreateModel(
            name="LineaPedido",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cantidad", models.PositiveIntegerField()),
                ("especificaciones", models.TextField(blank=True, null=True)),
                ("pedido", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lineas", to="pedidos.pedido")),
                ("producto", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="productos.producto")),
            ],
        ),
    ]
