from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("proveedores", "0004_rubro"),
    ]
    operations = [
        migrations.CreateModel(
            name="ProveedorParametro",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("clave", models.CharField(max_length=50, unique=True)),
                ("valor", models.CharField(max_length=200)),
                ("descripcion", models.TextField(blank=True, null=True)),
                ("activo", models.BooleanField(default=True)),
            ],
        ),
    ]
