from django.db import migrations, connection


def add_columns_if_missing(apps, schema_editor):
    table = 'proveedores_proveedor'
    existing_cols = set()
    with connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info('{table}')")
        existing = cursor.fetchall()
        existing_cols = {row[1] for row in existing}

    # Agregar cuit si falta
    if 'cuit' not in existing_cols:
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE proveedores_proveedor ADD COLUMN cuit varchar(13)")

    # Agregar rubro si falta
    if 'rubro' not in existing_cols:
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE proveedores_proveedor ADD COLUMN rubro varchar(50)")


def noop_reverse(apps, schema_editor):
    # No revertimos porque SQLite no soporta eliminar columnas fácilmente
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('proveedores', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(add_columns_if_missing, noop_reverse),
    ]
