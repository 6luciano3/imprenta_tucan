from django.db import migrations


def rename_columns(apps, schema_editor):
    cursor = schema_editor.connection.cursor()
    cursor.execute("PRAGMA table_info(clientes_cliente)")
    cols = [row[1] for row in cursor.fetchall()]

    # razon_social -> razónSocial
    if 'razon_social' in cols and 'razónSocial' not in cols:
        cursor.execute('ALTER TABLE clientes_cliente RENAME COLUMN razon_social TO "razónSocial"')

    # direccion -> dirección
    cursor.execute("PRAGMA table_info(clientes_cliente)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'direccion' in cols and 'dirección' not in cols:
        cursor.execute('ALTER TABLE clientes_cliente RENAME COLUMN direccion TO "dirección"')

    # estado -> estadoCliente
    cursor.execute("PRAGMA table_info(clientes_cliente)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'estado' in cols and 'estadoCliente' not in cols:
        cursor.execute('ALTER TABLE clientes_cliente RENAME COLUMN estado TO estadoCliente')


def reverse_rename_columns(apps, schema_editor):
    cursor = schema_editor.connection.cursor()
    cursor.execute("PRAGMA table_info(clientes_cliente)")
    cols = [row[1] for row in cursor.fetchall()]

    if 'estadoCliente' in cols and 'estado' not in cols:
        cursor.execute('ALTER TABLE clientes_cliente RENAME COLUMN estadoCliente TO estado')

    cursor.execute("PRAGMA table_info(clientes_cliente)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'dirección' in cols and 'direccion' not in cols:
        cursor.execute('ALTER TABLE clientes_cliente RENAME COLUMN "dirección" TO direccion')

    cursor.execute("PRAGMA table_info(clientes_cliente)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'razónSocial' in cols and 'razon_social' not in cols:
        cursor.execute('ALTER TABLE clientes_cliente RENAME COLUMN "razónSocial" TO razon_social')


class Migration(migrations.Migration):
    dependencies = [
        ('clientes', '0007_alter_cliente_dbcolumns'),
    ]

    operations = [
        migrations.RunPython(rename_columns, reverse_rename_columns),
    ]
