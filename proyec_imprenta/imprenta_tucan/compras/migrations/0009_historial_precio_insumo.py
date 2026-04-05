from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('compras', '0008_detalleremito_precio_unitario'),
        ('insumos', '0012_remove_insumo_precio'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HistorialPrecioInsumo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('precio_anterior', models.DecimalField(decimal_places=2, max_digits=10)),
                ('precio_nuevo', models.DecimalField(decimal_places=2, max_digits=10)),
                ('variacion_pct', models.DecimalField(blank=True, decimal_places=2, help_text='Variación porcentual respecto al precio anterior', max_digits=6, null=True)),
                ('origen', models.CharField(choices=[('manual', 'Actualización manual'), ('ajuste_masivo', 'Ajuste masivo'), ('remito', 'Recepción de remito'), ('sc', 'Solicitud de cotización')], default='manual', max_length=20)),
                ('motivo', models.CharField(blank=True, max_length=300)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('insumo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='historial_precios', to='insumos.insumo')),
                ('remito', models.ForeignKey(blank=True, help_text='Remito origen del cambio (si aplica)', null=True, on_delete=django.db.models.deletion.SET_NULL, to='compras.remito')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Historial de Precio',
                'verbose_name_plural': 'Historial de Precios',
                'ordering': ['-fecha'],
            },
        ),
    ]
