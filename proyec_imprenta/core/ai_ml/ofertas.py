"""
PI-1 — Generación de ofertas segmentadas por tier de cliente.

Punto único de entrada para la creación de OfertaPropuesta y para la
determinación del descuento aplicable.  Tanto la vista (views_combos) como
la tarea Celery (tarea_generar_ofertas) usan las mismas definiciones de tier,
eliminando la duplicación de fórmulas que causaba inconsistencias.

Catálogo de tiers (orden descendente):
  Premium    (score ≥ 90): 15 %  descuento
  Estratégico(score ≥ 60): 10 %  descuento
  Estándar   (score ≥ 30):  7 %  descuento
  Nuevo      (score  < 30):  5 %  descuento
"""
from django.utils import timezone

# ---------------------------------------------------------------------------
# Definición canónica de tiers — importada por views_combos y tasks
# ---------------------------------------------------------------------------
CATEGORIAS: list[dict] = [
    {
        'nombre': 'Premium',
        'score_min': 90,
        'score_max': None,
        'tipo': 'descuento',
        'descuento': 15,
        'titulo_prefijo': 'Combo Premium',
        'descripcion': 'Descuento exclusivo del 15% por ser nuestro cliente de mayor valor.',
    },
    {
        'nombre': 'Estrategico',
        'score_min': 60,
        'score_max': 90,
        'tipo': 'descuento',
        'descuento': 10,
        'titulo_prefijo': 'Combo Estrategico',
        'descripcion': 'Descuento especial del 10% por tu volumen y fidelidad.',
    },
    {
        'nombre': 'Estandar',
        'score_min': 30,
        'score_max': 60,
        'tipo': 'promocion',
        'descuento': 7,
        'titulo_prefijo': 'Combo Estandar',
        'descripcion': 'Promocion del 7% en tu proximo pedido.',
    },
    {
        'nombre': 'Nuevo',
        'score_min': None,
        'score_max': 30,
        'tipo': 'promocion',
        'descuento': 5,
        'titulo_prefijo': 'Combo Bienvenida',
        'descripcion': 'Descuento de bienvenida del 5% en tu primer combo.',
    },
]


def categoria_por_score(score: float) -> dict | None:
    """Retorna la categoría de tier correspondiente al score, o None si no aplica."""
    for cat in CATEGORIAS:
        min_ok = cat['score_min'] is None or score >= cat['score_min']
        max_ok = cat['score_max'] is None or score < cat['score_max']
        if min_ok and max_ok:
            return cat
    return None


def descuento_por_score(score: float) -> int:
    """
    Descuento (%) según el tier del score.
    Función única usada tanto por generar_combo_para_cliente como por
    generar_ofertas_segmentadas, garantizando consistencia total.
    """
    cat = categoria_por_score(score)
    return cat['descuento'] if cat else 5


# ---------------------------------------------------------------------------
# Lógica de generación de OfertaPropuesta
# ---------------------------------------------------------------------------

def generar_ofertas_segmentadas() -> dict:
    """
    Genera una OfertaPropuesta por cliente según su categoría de score.
    Retorna {'generadas': int, 'periodo': str}.
    """
    from configuracion.models import Parametro
    from automatizacion.models import RankingCliente, OfertaPropuesta
    # Deferred import para evitar circularidad a nivel de módulo
    from automatizacion.views_combos import generar_combo_para_cliente

    now = timezone.now()
    periodo_conf = Parametro.get('RANKING_PERIODICIDAD', 'mensual')
    periodo_str = (
        now.strftime('%Y-%m')
        if periodo_conf != 'trimestral'
        else f"{now.year}-Q{(now.month - 1) // 3 + 1}"
    )

    generadas = 0
    for rc in RankingCliente.objects.select_related('cliente').all():
        cliente = rc.cliente
        score = float(rc.score or 0)

        categoria = categoria_por_score(score)
        if not categoria:
            continue

        ya_existe = OfertaPropuesta.objects.filter(
            cliente=cliente,
            tipo=categoria['tipo'],
            periodo=periodo_str,
        ).exists()
        if ya_existe:
            continue

        try:
            combo = generar_combo_para_cliente(cliente)
        except Exception:
            combo = None

        if combo and combo.comboofertaproducto_set.exists():
            nombres_productos = list(
                combo.comboofertaproducto_set
                .select_related('producto')
                .values_list('producto__nombreProducto', flat=True)[:3]
            )
            nombres_str = ' + '.join(n[:25] for n in nombres_productos)
            titulo = f"{categoria['titulo_prefijo']} – {nombres_str}"
            if len(titulo) > 118:
                titulo = titulo[:115] + '...'
            descripcion = (
                f"{categoria['descripcion']} "
                f"Incluye: {', '.join(nombres_productos)}."
            )
            parametros_oferta = {
                'descuento': round(float(combo.descuento), 1),
                'categoria': categoria['nombre'],
                'productos': nombres_productos,
                'combo_id': combo.pk,
            }
        else:
            titulo = categoria['titulo_prefijo']
            descripcion = categoria['descripcion']
            parametros_oferta = {
                'descuento': categoria['descuento'],
                'categoria': categoria['nombre'],
            }

        OfertaPropuesta.objects.create(
            cliente=cliente,
            titulo=titulo,
            descripcion=descripcion,
            tipo=categoria['tipo'],
            estado='pendiente',
            periodo=periodo_str,
            score_al_generar=min(float(rc.score or 0), 100.0),
            parametros=parametros_oferta,
        )
        generadas += 1

    return {'generadas': generadas, 'periodo': periodo_str}
