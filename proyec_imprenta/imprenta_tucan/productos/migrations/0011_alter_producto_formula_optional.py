from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0008_alter_recetaproducto_insumos'),
        ('productos', '0010_unidadmedida_fk_to_configuracion'),
    ]

    operations = [
        migrations.AlterField(
            model_name='producto',
            name='formula',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='productos',
                to='configuracion.formula',
                help_text='Fórmula para calcular los insumos de este producto (opcional)',
            ),
        ),
    ]
