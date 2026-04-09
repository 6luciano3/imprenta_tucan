from django.db import migrations, models


def poblar_anulado(apps, schema_editor):
    """Marca como anulados los remitos que tienen el prefijo [ANULADO] en observaciones."""
    Remito = apps.get_model('compras', 'Remito')
    Remito.objects.filter(observaciones__startswith='[ANULADO]').update(anulado=True)


class Migration(migrations.Migration):

    dependencies = [
        ('compras', '0011_ordencompra_token_proveedor'),
    ]

    operations = [
        migrations.AddField(
            model_name='remito',
            name='anulado',
            field=models.BooleanField(
                default=False,
                help_text='Indica si el remito fue anulado (baja lógica)',
            ),
        ),
        migrations.RunPython(poblar_anulado, migrations.RunPython.noop),
    ]
