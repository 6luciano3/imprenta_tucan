from django.db import transaction
from insumos.models import Insumo
from productos.models import Producto, ProductoInsumo
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
django.setup()


def get_insumo(code=None, name_contains=None):
    qs = Insumo.objects.all()
    if code:
        try:
            return qs.get(codigo=code)
        except Insumo.DoesNotExist:
            pass
    if name_contains:
        return qs.filter(nombre__icontains=name_contains).order_by('idInsumo').first()
    return None


# Insumos posibles
PLANCHAS_A3 = get_insumo(code='IN-005') or get_insumo(name_contains='Planchas Presensibilizadas A3')
PLANCHAS_TERMICAS_A3 = get_insumo(code='IN-007') or get_insumo(name_contains='Planchas Térmicas')
BARNIZ_BRILLANTE_1KG = get_insumo(code='IN-018') or get_insumo(name_contains='Barniz Brillante UV')
BARNIZ_MATE_1KG = get_insumo(code='IN-019') or get_insumo(name_contains='Barniz Mate UV')
BARNIZ_MAQUINA_1L = get_insumo(code='IN-058') or get_insumo(name_contains='Barniz de Máquina')
FILM_LAMINADO = get_insumo(code='IN-034') or get_insumo(name_contains='Film Antiadherente')
LAMINADO_BRILLANTE = get_insumo(code='IN-101') or get_insumo(name_contains='Laminado Brillante')
LAMINADO_MATE = get_insumo(code='IN-102') or get_insumo(name_contains='Laminado Mate')


@transaction.atomic
def poblar_bom():
    total_prods = 0
    total_rel = 0

    productos = list(Producto.objects.all())

    for p in productos:
        total_prods += 1
        name = (p.nombreProducto or '').lower()
        cambios = 0

        # Heurística por tipo de producto
        # Nota: ProductoInsumo es por unidad de producto. Para insumos de "arranque" (planchas),
        # aproximamos con una fracción por unidad asumiendo tirada estándar de 100 unidades.
        #  - Doble faz 4/4 => 8 planchas por trabajo => 0.08 por unidad
        #  - Simple faz 4/0 => 4 planchas por trabajo => 0.04 por unidad
        plates_per_unit_double = Decimal('0.08')
        plates_per_unit_single = Decimal('0.04')

        # Barniz por unidad (aprox. en kg o L por unidad)
        varnish_unit_small = Decimal('0.02')
        varnish_unit_medium = Decimal('0.03')
        varnish_unit_large = Decimal('0.05')
        film_unit_small = Decimal('0.02')
        film_unit_medium = Decimal('0.03')

        # Reglas
        if 'tarjeta' in name:
            # Tarjetas color: barniz (premium) y planchas doble faz
            if 'premium' in name or 'laminada' in name or 'laminado' in name:
                ins_barniz = BARNIZ_BRILLANTE_1KG or BARNIZ_MATE_1KG
                qty_barniz = varnish_unit_small
                if ins_barniz:
                    ProductoInsumo.objects.update_or_create(
                        producto=p, insumo=ins_barniz,
                        defaults={'cantidad_por_unidad': qty_barniz}
                    )
                    cambios += 1
                # Laminado: preferir insumos dedicados (brillante/mate); fallback a film
                lam_ins = None
                if 'mate' in name and LAMINADO_MATE:
                    lam_ins = LAMINADO_MATE
                elif LAMINADO_BRILLANTE:
                    lam_ins = LAMINADO_BRILLANTE
                elif FILM_LAMINADO:
                    lam_ins = FILM_LAMINADO
                if lam_ins:
                    ProductoInsumo.objects.update_or_create(
                        producto=p, insumo=lam_ins,
                        defaults={'cantidad_por_unidad': film_unit_small}
                    )
                    cambios += 1
            # Planchas doble faz
            ins_pl = PLANCHAS_A3 or PLANCHAS_TERMICAS_A3
            if ins_pl:
                ProductoInsumo.objects.update_or_create(
                    producto=p, insumo=ins_pl,
                    defaults={'cantidad_por_unidad': plates_per_unit_double}
                )
                cambios += 1

        elif 'afiche a3' in name:
            # Afiche A3: simple faz, barniz de máquina
            if BARNIZ_MAQUINA_1L:
                ProductoInsumo.objects.update_or_create(
                    producto=p, insumo=BARNIZ_MAQUINA_1L,
                    defaults={'cantidad_por_unidad': varnish_unit_small}
                )
                cambios += 1
            ins_pl = PLANCHAS_A3 or PLANCHAS_TERMICAS_A3
            if ins_pl:
                ProductoInsumo.objects.update_or_create(
                    producto=p, insumo=ins_pl,
                    defaults={'cantidad_por_unidad': plates_per_unit_single}
                )
                cambios += 1

        elif 'afiche a2' in name or 'afiche a1' in name or 'poster' in name:
            # Formatos grandes: simple faz, algo más de barniz
            if BARNIZ_MAQUINA_1L:
                ProductoInsumo.objects.update_or_create(
                    producto=p, insumo=BARNIZ_MAQUINA_1L,
                    defaults={'cantidad_por_unidad': varnish_unit_medium}
                )
                cambios += 1
            ins_pl = PLANCHAS_A3 or PLANCHAS_TERMICAS_A3
            if ins_pl:
                ProductoInsumo.objects.update_or_create(
                    producto=p, insumo=ins_pl,
                    defaults={'cantidad_por_unidad': plates_per_unit_single}
                )
                cambios += 1

        elif 'folleto' in name or 'díptico' in name or 'diptico' in name or 'tríptico' in name or 'triptico' in name:
            # Folletos/dípticos/trípticos color doble faz
            ins_barniz = BARNIZ_BRILLANTE_1KG or BARNIZ_MATE_1KG
            if ins_barniz:
                ProductoInsumo.objects.update_or_create(
                    producto=p, insumo=ins_barniz,
                    defaults={'cantidad_por_unidad': varnish_unit_small}
                )
                cambios += 1
            ins_pl = PLANCHAS_A3 or PLANCHAS_TERMICAS_A3
            if ins_pl:
                ProductoInsumo.objects.update_or_create(
                    producto=p, insumo=ins_pl,
                    defaults={'cantidad_por_unidad': plates_per_unit_double}
                )
                cambios += 1

        elif 'carpeta' in name:
            # Carpeta en cartulina, barniz mate, doble faz
            if BARNIZ_MATE_1KG:
                ProductoInsumo.objects.update_or_create(
                    producto=p, insumo=BARNIZ_MATE_1KG,
                    defaults={'cantidad_por_unidad': varnish_unit_large}
                )
                cambios += 1
            # Laminado si se menciona
            if 'laminado' in name:
                lam_ins = LAMINADO_BRILLANTE or FILM_LAMINADO
                if 'mate' in name and LAMINADO_MATE:
                    lam_ins = LAMINADO_MATE
                if lam_ins:
                    ProductoInsumo.objects.update_or_create(
                        producto=p, insumo=lam_ins,
                        defaults={'cantidad_por_unidad': film_unit_medium}
                    )
                    cambios += 1
            ins_pl = PLANCHAS_A3 or PLANCHAS_TERMICAS_A3
            if ins_pl:
                ProductoInsumo.objects.update_or_create(
                    producto=p, insumo=ins_pl,
                    defaults={'cantidad_por_unidad': plates_per_unit_double}
                )
                cambios += 1

        elif 'revista' in name or 'catálogo' in name or 'catalogo' in name or 'libro' in name or 'manual' in name:
            # Editorial: asumir doble faz, algo de barniz brillante
            ins_barniz = BARNIZ_BRILLANTE_1KG
            if ins_barniz:
                ProductoInsumo.objects.update_or_create(
                    producto=p, insumo=ins_barniz,
                    defaults={'cantidad_por_unidad': varnish_unit_small}
                )
                cambios += 1
            ins_pl = PLANCHAS_A3 or PLANCHAS_TERMICAS_A3
            if ins_pl:
                ProductoInsumo.objects.update_or_create(
                    producto=p, insumo=ins_pl,
                    defaults={'cantidad_por_unidad': plates_per_unit_double}
                )
                cambios += 1

        elif 'menú' in name or 'menu' in name:
            # Menú plastificado: algo de barniz máquina y planchas simple
            if BARNIZ_MAQUINA_1L:
                ProductoInsumo.objects.update_or_create(
                    producto=p, insumo=BARNIZ_MAQUINA_1L,
                    defaults={'cantidad_por_unidad': varnish_unit_small}
                )
                cambios += 1
            # Laminado si aplica
            if 'laminado' in name:
                lam_ins = LAMINADO_BRILLANTE or FILM_LAMINADO
                if 'mate' in name and LAMINADO_MATE:
                    lam_ins = LAMINADO_MATE
                if lam_ins:
                    ProductoInsumo.objects.update_or_create(
                        producto=p, insumo=lam_ins,
                        defaults={'cantidad_por_unidad': film_unit_small}
                    )
                    cambios += 1
            ins_pl = PLANCHAS_A3 or PLANCHAS_TERMICAS_A3
            if ins_pl:
                ProductoInsumo.objects.update_or_create(
                    producto=p, insumo=ins_pl,
                    defaults={'cantidad_por_unidad': plates_per_unit_single}
                )
                cambios += 1

        # Reglas transversales por palabras clave (UV sectorizado, laca UV, etc.)
        if 'uv' in name:
            # aplicar barniz brillante si menciona UV o "laca uv"
            if BARNIZ_BRILLANTE_1KG:
                ProductoInsumo.objects.update_or_create(
                    producto=p, insumo=BARNIZ_BRILLANTE_1KG,
                    defaults={'cantidad_por_unidad': varnish_unit_small}
                )
                # contar cambio solo si no se contó arriba; simplificamos sumando 1
                cambios += 1
        if 'sectorizado' in name and BARNIZ_BRILLANTE_1KG:
            ProductoInsumo.objects.update_or_create(
                producto=p, insumo=BARNIZ_BRILLANTE_1KG,
                defaults={'cantidad_por_unidad': varnish_unit_small}
            )
            cambios += 1

        # Reporte por producto
        if cambios:
            print(f"[BOM] {p.nombreProducto}: {cambios} filas (barniz/planchas)")
        else:
            print(f"[BOM] {p.nombreProducto}: sin cambios")
        total_rel += cambios

    print("\nResumen BOM:")
    print(f" - Productos procesados: {total_prods}")
    print(f" - Relación producto-insumo creadas/actualizadas: {total_rel}")


if __name__ == '__main__':
    poblar_bom()
