from django.db import transaction, connection, IntegrityError
from insumos.models import Insumo
from proveedores.models import Proveedor
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()


@transaction.atomic
def poblar_laminados():
    try:
        prov, _ = Proveedor.objects.get_or_create(
            nombre='Laminados Argentina SA',
            defaults={
                'cuit': '30-00000001-1',
                'email': 'ventas@laminados.local',
                'telefono': '+54 11 5000-0000',
                'direccion': 'Av. Industrial 1234, CABA',
                'rubro': 'Industria Gráfica - Laminados',
                'activo': True,
            }
        )
    except IntegrityError:
        # Fallback para bases con columnas extra NOT NULL en proveedores_proveedor
        if connection.connection is None:
            connection.ensure_connection()
        cur = connection.connection.cursor()
        try:
            cur.execute("PRAGMA table_info('proveedores_proveedor')")
            cols = {r[1] for r in cur.fetchall()}

            columns = ['nombre', 'cuit', 'email', 'telefono', 'direccion', 'rubro', 'activo']
            values = [
                'Laminados Argentina SA',
                '30-00000001-1',
                'ventas@laminados.local',
                '+54 11 5000-0000',
                'Av. Industrial 1234, CABA',
                'Industria Gráfica - Laminados',
                1,
            ]
            if 'apellido' in cols:
                columns.append('apellido')
                values.append('')
            if 'empresa' in cols:
                columns.append('empresa')
                values.append('Laminados Argentina SA')
            columns.append('fecha_creacion')
            placeholders = ', '.join(['?'] * (len(columns) - 1)) + ", CURRENT_TIMESTAMP"
            sql = f"INSERT INTO proveedores_proveedor ({', '.join(columns)}) VALUES ({placeholders})"
            cur.execute(sql, tuple(values))
            inserted_id = cur.lastrowid
        finally:
            cur.close()
        prov = Proveedor.objects.get(pk=inserted_id)

    datos = [
        {
            'codigo': 'IN-101',
            'nombre': 'Laminado Brillante Rollo 32 mic',
            'categoria': 'Laminados',
            'precio': Decimal('1200'),
            'stock': 20,
        },
        {
            'codigo': 'IN-102',
            'nombre': 'Laminado Mate Rollo 32 mic',
            'categoria': 'Laminados',
            'precio': Decimal('1300'),
            'stock': 20,
        },
    ]

    creados, actualizados = 0, 0
    for d in datos:
        ins, created = Insumo.objects.update_or_create(
            codigo=d['codigo'],
            defaults={
                'nombre': d['nombre'],
                'proveedor': prov,
                'cantidad': d['stock'],
                'precio_unitario': d['precio'],
                'categoria': d['categoria'],
                'stock': d['stock'],
                'precio': d['precio'],
                'activo': True,
            }
        )
        if created:
            creados += 1
        else:
            actualizados += 1
        print(f" - {'[+]' if created else '[~]'} {ins.codigo} {ins.nombre}")

    print('\nResumen:')
    print(f" - Insumos creados: {creados}")
    print(f" - Insumos actualizados: {actualizados}")


if __name__ == '__main__':
    poblar_laminados()
