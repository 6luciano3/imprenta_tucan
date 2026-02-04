from django.db import migrations


def rename_nombre_to_nombreUsuario(apps, schema_editor):
    cursor = schema_editor.connection.cursor()
    cursor.execute("PRAGMA table_info(usuarios_usuario)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'nombre' in cols and 'nombreUsuario' not in cols:
        cursor.execute("ALTER TABLE usuarios_usuario RENAME COLUMN nombre TO nombreUsuario")


def reverse_rename_nombre_to_nombreUsuario(apps, schema_editor):
    cursor = schema_editor.connection.cursor()
    cursor.execute("PRAGMA table_info(usuarios_usuario)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'nombreUsuario' in cols and 'nombre' not in cols:
        cursor.execute("ALTER TABLE usuarios_usuario RENAME COLUMN nombreUsuario TO nombre")


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0012_alter_usuario_nombre_dbcolumn'),
    ]

    operations = [
        migrations.RunPython(rename_nombre_to_nombreUsuario, reverse_rename_nombre_to_nombreUsuario),
    ]
