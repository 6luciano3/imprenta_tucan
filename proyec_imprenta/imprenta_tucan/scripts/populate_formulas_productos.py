from django.db import transaction
from insumos.models import Insumo
from productos.models import Producto
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()


def get_insumo_by_code_or_name(code: str = None, name_contains: str = None):
    qs = Insumo.objects.all()
    if code:
        try:
            return qs.get(codigo=code)
        except Insumo.DoesNotExist:
            pass
    if name_contains:
        return qs.filter(nombre__icontains=name_contains).order_by('idInsumo').first()
    return None


@transaction.atomic
def set_formulas():
    updates = []

    # Referencias de insumos típicos
    papel_a3_150 = get_insumo_by_code_or_name(
        code='IN-021') or get_insumo_by_code_or_name(name_contains='Ilustración 150 g A3')
    papel_a3_300 = get_insumo_by_code_or_name(
        code='IN-022') or get_insumo_by_code_or_name(name_contains='Ilustración 300 g A3')
    tinta_negra = get_insumo_by_code_or_name(code='IN-001') or get_insumo_by_code_or_name(name_contains='Tinta Negra')

    # 1) Folleto A4 Color -> 2 unidades por pliego A3, merma 8%, tinta 30g/pliego +5%
    try:
        p = Producto.objects.get(nombreProducto__iexact='Folleto A4 Color')
        p.unidades_por_pliego = 2
        p.merma_papel = Decimal('0.08')
        if papel_a3_150:
            p.papel_insumo = papel_a3_150
        p.gramos_por_pliego = Decimal('30')
        p.merma_tinta = Decimal('0.05')
        if tinta_negra:
            p.tinta_insumo = tinta_negra
        p.save()
        updates.append(('Folleto A4 Color', p.idProducto))
    except Producto.DoesNotExist:
        pass

    # 2) Tarjeta Personal Color -> 24 unidades por pliego A3, merma 10%, tinta 20g/pliego +5%
    try:
        p = Producto.objects.get(nombreProducto__iexact='Tarjeta Personal Color')
        p.unidades_por_pliego = 24
        p.merma_papel = Decimal('0.10')
        if papel_a3_300:
            p.papel_insumo = papel_a3_300
        p.gramos_por_pliego = Decimal('20')
        p.merma_tinta = Decimal('0.05')
        if tinta_negra:
            p.tinta_insumo = tinta_negra
        p.save()
        updates.append(('Tarjeta Personal Color', p.idProducto))
    except Producto.DoesNotExist:
        pass

    # 3) Afiche A3 Color -> 1 unidad por pliego A3, merma 5%, tinta 25g/pliego +5%
    try:
        p = Producto.objects.get(nombreProducto__iexact='Afiche A3 Color')
        p.unidades_por_pliego = 1
        p.merma_papel = Decimal('0.05')
        if papel_a3_150:
            p.papel_insumo = papel_a3_150
        p.gramos_por_pliego = Decimal('25')
        p.merma_tinta = Decimal('0.05')
        if tinta_negra:
            p.tinta_insumo = tinta_negra
        p.save()
        updates.append(('Afiche A3 Color', p.idProducto))
    except Producto.DoesNotExist:
        pass

    print('Parámetros de fórmula actualizados para:')
    for name, pid in updates:
        print(f" - {name} (id={pid})")
    if not updates:
        print('No se encontró ningún producto objetivo para actualizar.')


if __name__ == '__main__':
    set_formulas()
