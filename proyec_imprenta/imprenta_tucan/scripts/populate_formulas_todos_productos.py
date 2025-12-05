from django.db import transaction
from insumos.models import Insumo
from productos.models import Producto
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()


def get(code=None, name_contains=None):
    qs = Insumo.objects.all()
    if code:
        try:
            return qs.get(codigo=code)
        except Insumo.DoesNotExist:
            pass
    if name_contains:
        return qs.filter(nombre__icontains=name_contains).order_by('idInsumo').first()
    return None


# Insumos de referencia
TIN_N = get(code='IN-001') or get(name_contains='Tinta Negra')
PAP_ILU_150_A3 = get(code='IN-021') or get(name_contains='Ilustración 150 g A3')
PAP_ILU_300_A3 = get(code='IN-022') or get(name_contains='Ilustración 300 g A3')
PAP_CARTULINA_350 = get(code='IN-023') or get(name_contains='Duplex 350')
PAP_OBRA_80_A4 = get(code='IN-024') or get(name_contains='Obra 80 g A4')
PAP_BOND_90_A4 = get(code='IN-025') or get(name_contains='Bond 90 g A4')
PAP_AUTOADH_A4 = get(code='IN-055') or get(name_contains='Autoadhesivo A4')
PAP_KRAFT_80 = get(code='IN-056') or get(name_contains='Kraft 80 g')
PAP_AUTOCO_BLANCO_A4 = get(code='IN-071') or get(name_contains='Autocopiativo Blanco A4')
PAP_COUCHE_115 = get(code='IN-100') or get(name_contains='Couché Brillante 115')


@transaction.atomic
def asignar_formulas():
    total = 0
    actualizados = 0

    productos = list(Producto.objects.all())

    for p in productos:
        total += 1
        name = (p.nombreProducto or '').lower()

        # Defaults
        up = 1  # unidades por pliego
        mp = Decimal('0.06')  # merma papel
        papel = PAP_COUCHE_115 or PAP_ILU_150_A3
        gp = Decimal('25')  # gramos por pliego
        mt = Decimal('0.05')  # merma tinta
        tinta = TIN_N

        # Reglas por tipo/nombre
        if 'tarjeta' in name:
            up = 24
            mp = Decimal('0.10')
            papel = PAP_ILU_300_A3 or PAP_CARTULINA_350 or PAP_COUCHE_115
            gp = Decimal('20')
        elif 'afiche a3' in name:
            up = 1
            mp = Decimal('0.05')
            papel = PAP_ILU_150_A3 or PAP_COUCHE_115
            gp = Decimal('25')
        elif 'afiche a2' in name or 'afiche a1' in name or 'poster' in name:
            up = 1
            mp = Decimal('0.07')
            papel = PAP_COUCHE_115 or PAP_ILU_150_A3
            gp = Decimal('40')
        elif 'tríptico' in name or 'triptico' in name:
            up = 1
            mp = Decimal('0.08')
            papel = PAP_ILU_150_A3
            gp = Decimal('30')
        elif 'díptico' in name or 'diptico' in name:
            up = 2
            mp = Decimal('0.08')
            papel = PAP_ILU_150_A3
            gp = Decimal('28')
        elif 'folleto' in name and 'a5' in name:
            up = 4
            mp = Decimal('0.08')
            papel = PAP_OBRA_80_A4 or PAP_ILU_150_A3
            gp = Decimal('22')
        elif 'folleto' in name and 'a4' in name:
            up = 2
            mp = Decimal('0.08')
            papel = PAP_ILU_150_A3
            gp = Decimal('30')
        elif 'catálogo' in name or 'catalogo' in name or 'revista' in name or 'libro' in name or 'manual' in name:
            up = 1
            mp = Decimal('0.06')
            papel = PAP_COUCHE_115 or PAP_OBRA_80_A4
            gp = Decimal('35')
        elif 'carpeta' in name:
            up = 1
            mp = Decimal('0.10')
            papel = PAP_ILU_300_A3 or PAP_CARTULINA_350
            gp = Decimal('30')
        elif 'membrete' in name:
            up = 1
            mp = Decimal('0.05')
            papel = PAP_BOND_90_A4 or PAP_OBRA_80_A4
            gp = Decimal('10')
        elif 'sobre' in name:
            up = 1
            mp = Decimal('0.05')
            papel = PAP_KRAFT_80 or PAP_BOND_90_A4
            gp = Decimal('8')
        elif 'calendario de pared' in name and 'a3' in name:
            up = 1
            mp = Decimal('0.06')
            papel = PAP_ILU_150_A3
            gp = Decimal('25')
        elif 'calendario de escritorio' in name or 'bolsillo' in name:
            up = 6
            mp = Decimal('0.08')
            papel = PAP_ILU_300_A3 or PAP_ILU_150_A3
            gp = Decimal('15')
        elif 'bloc de notas' in name:
            up = 2
            mp = Decimal('0.07')
            papel = PAP_OBRA_80_A4
            gp = Decimal('10')
        elif 'talonario' in name:
            up = 1
            mp = Decimal('0.07')
            papel = PAP_AUTOCO_BLANCO_A4 or PAP_OBRA_80_A4
            gp = Decimal('12')
        elif 'etiqueta' in name:
            up = 6
            mp = Decimal('0.05')
            papel = PAP_AUTOADH_A4 or PAP_COUCHE_115
            gp = Decimal('8')
        elif 'caja plegadiza' in name:
            up = 1
            mp = Decimal('0.10')
            papel = PAP_CARTULINA_350 or PAP_ILU_300_A3
            gp = Decimal('20')
        elif 'menú' in name or 'menu' in name:
            up = 1
            mp = Decimal('0.06')
            papel = PAP_ILU_150_A3
            gp = Decimal('28')

        # Aplicar si tenemos referencias
        changed = False
        if tinta and (p.tinta_insumo_id != getattr(tinta, 'idInsumo', None)):
            p.tinta_insumo = tinta
            changed = True
        if papel and (p.papel_insumo_id != getattr(papel, 'idInsumo', None)):
            p.papel_insumo = papel
            changed = True

        # Set numéricos
        if p.unidades_por_pliego != up:
            p.unidades_por_pliego = up
            changed = True
        if p.merma_papel != mp:
            p.merma_papel = mp
            changed = True
        if p.gramos_por_pliego != gp:
            p.gramos_por_pliego = gp
            changed = True
        if p.merma_tinta != mt:
            p.merma_tinta = mt
            changed = True

        if changed:
            p.save()
            actualizados += 1
            print(f"[✓] {p.nombreProducto} -> up={up}, mp={mp}, papel={papel and papel.codigo}, gp={gp}, mt={mt}, tinta={tinta and tinta.codigo}")
        else:
            print(f"[ ] {p.nombreProducto} (sin cambios)")

    # Resumen
    faltantes = Producto.objects.filter(papel_insumo__isnull=True).count() + \
        Producto.objects.filter(tinta_insumo__isnull=True).count()
    print("\nResumen:")
    print(f" - Productos procesados: {total}")
    print(f" - Productos actualizados: {actualizados}")
    print(f" - Campos de fórmula faltantes (papel o tinta): {faltantes}")


if __name__ == '__main__':
    asignar_formulas()
