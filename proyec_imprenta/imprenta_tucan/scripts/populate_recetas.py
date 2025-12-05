from django.db import transaction
from insumos.models import Insumo
from productos.models import Producto
from configuracion.models import RecetaProducto
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()


# Este script crea RecetaProducto para cada producto que tenga fórmula y asocia insumos principales
# Puedes modificar la lógica para agregar más insumos según tu modelo de negocio


@transaction.atomic
def poblar_recetas():
    creados = 0
    actualizados = 0
    for producto in Producto.objects.all():
        # Busca insumos principales (ajusta según tu modelo)
        insumos = []
        if hasattr(producto, 'papel_insumo') and producto.papel_insumo:
            insumos.append(producto.papel_insumo)
        if hasattr(producto, 'tinta_insumo') and producto.tinta_insumo:
            insumos.append(producto.tinta_insumo)
        if not insumos:
            continue
        receta, created = RecetaProducto.objects.get_or_create(
            producto=producto,
            formula=None,
            defaults={
                'descripcion': f'Receta generada automáticamente para {producto}',
                'activo': True,
            }
        )
        receta.insumos.set(insumos)
        receta.save()
        if created:
            creados += 1
        else:
            actualizados += 1
        print(f"{'[+]' if created else '[*]'} {receta}")
    print(f"Recetas creadas: {creados}, actualizadas: {actualizados}")


if __name__ == '__main__':
    poblar_recetas()
