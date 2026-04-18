from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insumos', '0014_proyeccioninsumo_fuente'),
    ]

    operations = [
        # Eliminar campo deprecated Insumo.cantidad
        migrations.RemoveField(
            model_name='insumo',
            name='cantidad',
        ),
        # Índices en ProyeccionInsumo
        migrations.AddIndex(
            model_name='proyeccioninsumo',
            index=models.Index(fields=['periodo'], name='proyeccion_periodo_idx'),
        ),
        migrations.AddIndex(
            model_name='proyeccioninsumo',
            index=models.Index(fields=['estado'], name='proyeccion_estado_idx'),
        ),
        migrations.AddIndex(
            model_name='proyeccioninsumo',
            index=models.Index(fields=['insumo', 'estado'], name='proyeccion_insumo_estado_idx'),
        ),
        # Índice en ConsumoRealInsumo
        migrations.AddIndex(
            model_name='consumorealinsumo',
            index=models.Index(fields=['insumo', 'periodo'], name='consumo_insumo_periodo_idx'),
        ),
    ]
