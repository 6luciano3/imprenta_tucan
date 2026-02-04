from django.db import migrations


def populate_rubro_fk(apps, schema_editor):
    Rubro = apps.get_model('proveedores', 'Rubro')
    Proveedor = apps.get_model('proveedores', 'Proveedor')

    # Crear Rubros desde valores textuales y asignar FK
    for proveedor in Proveedor.objects.all():
        nombre_txt = (proveedor.rubro or '').strip()
        if not nombre_txt:
            continue
        rubro_obj, _ = Rubro.objects.get_or_create(
            nombre__iexact=nombre_txt,
            defaults={'nombre': nombre_txt, 'activo': True}
        )
        # Si get_or_create con nombre__iexact no soporta lookup en defaults, resolver manualmente
        if not _:
            # Cuando la consulta anterior no crea por el lookup, intentar obtener case-insensitive
            try:
                rubro_obj = Rubro.objects.get(nombre__iexact=nombre_txt)
            except Rubro.DoesNotExist:
                rubro_obj = Rubro.objects.create(nombre=nombre_txt, activo=True)
        proveedor.rubro_fk = rubro_obj
        proveedor.save(update_fields=['rubro_fk'])


def reverse_populate_rubro_fk(apps, schema_editor):
    # No revertimos creación de rubros; limpiamos FK si existiera
    Proveedor = apps.get_model('proveedores', 'Proveedor')
    for proveedor in Proveedor.objects.exclude(rubro_fk=None):
        proveedor.rubro = proveedor.rubro_fk.nombre
        proveedor.rubro_fk = None
        proveedor.save(update_fields=['rubro', 'rubro_fk'])


class Migration(migrations.Migration):
    dependencies = [
        ('proveedores', '0008_proveedor_rubro_fk'),
    ]

    operations = [
        migrations.RunPython(populate_rubro_fk, reverse_populate_rubro_fk),
    ]
