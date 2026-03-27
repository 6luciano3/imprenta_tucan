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


def get_categorias() -> list[dict]:
    """
    Retorna la lista de tiers leyendo los parámetros de BD (Parametro).
    Usa los valores hardcodeados de CATEGORIAS como fallback cuando el parámetro
    aún no fue configurado.
    """
    try:
        from configuracion.models import Parametro
    except Exception:
        return CATEGORIAS

    defaults = {cat['nombre']: cat for cat in CATEGORIAS}

    def _get_int(clave, fallback):
        v = Parametro.get(clave, None)
        if v is None:
            return fallback
        try:
            return int(v)
        except (ValueError, TypeError):
            return fallback

    def _get_str(clave, fallback):
        v = Parametro.get(clave, None)
        return v if v is not None else fallback

    premium_d = defaults['Premium']
    estrategico_d = defaults['Estrategico']
    estandar_d = defaults['Estandar']
    nuevo_d = defaults['Nuevo']

    premium_score_min = _get_int('OFERTA_TIER_PREMIUM_SCORE_MIN', premium_d['score_min'])
    estrategico_score_min = _get_int('OFERTA_TIER_ESTRATEGICO_SCORE_MIN', estrategico_d['score_min'])
    estandar_score_min = _get_int('OFERTA_TIER_ESTANDAR_SCORE_MIN', estandar_d['score_min'])

    return [
        {
            'nombre': 'Premium',
            'score_min': premium_score_min,
            'score_max': None,
            'tipo': 'descuento',
            'descuento': _get_int('OFERTA_TIER_PREMIUM_DESCUENTO', premium_d['descuento']),
            'titulo_prefijo': _get_str('OFERTA_TIER_PREMIUM_TITULO', premium_d['titulo_prefijo']),
            'descripcion': _get_str('OFERTA_TIER_PREMIUM_DESCRIPCION', premium_d['descripcion']),
        },
        {
            'nombre': 'Estrategico',
            'score_min': estrategico_score_min,
            'score_max': premium_score_min,
            'tipo': 'descuento',
            'descuento': _get_int('OFERTA_TIER_ESTRATEGICO_DESCUENTO', estrategico_d['descuento']),
            'titulo_prefijo': _get_str('OFERTA_TIER_ESTRATEGICO_TITULO', estrategico_d['titulo_prefijo']),
            'descripcion': _get_str('OFERTA_TIER_ESTRATEGICO_DESCRIPCION', estrategico_d['descripcion']),
        },
        {
            'nombre': 'Estandar',
            'score_min': estandar_score_min,
            'score_max': estrategico_score_min,
            'tipo': 'promocion',
            'descuento': _get_int('OFERTA_TIER_ESTANDAR_DESCUENTO', estandar_d['descuento']),
            'titulo_prefijo': _get_str('OFERTA_TIER_ESTANDAR_TITULO', estandar_d['titulo_prefijo']),
            'descripcion': _get_str('OFERTA_TIER_ESTANDAR_DESCRIPCION', estandar_d['descripcion']),
        },
        {
            'nombre': 'Nuevo',
            'score_min': None,
            'score_max': estandar_score_min,
            'tipo': 'promocion',
            'descuento': _get_int('OFERTA_TIER_NUEVO_DESCUENTO', nuevo_d['descuento']),
            'titulo_prefijo': _get_str('OFERTA_TIER_NUEVO_TITULO', nuevo_d['titulo_prefijo']),
            'descripcion': _get_str('OFERTA_TIER_NUEVO_DESCRIPCION', nuevo_d['descripcion']),
        },
    ]


def categoria_por_score(score: float) -> dict | None:
    """Retorna la categoría de tier correspondiente al score, o None si no aplica."""
    for cat in get_categorias():
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

# Días mínimos entre una oferta enviada y la siguiente para el mismo cliente.
# Configurable via Parametro('OFERTA_CADENCIA_MINIMA_DIAS'); defecto: 15.
_CADENCIA_MINIMA_DIAS_DEFAULT = 15


def generar_ofertas_segmentadas() -> dict:
    """
    Genera una OfertaPropuesta por cliente según su categoría de score.
    Retorna {'generadas': int, 'periodo': str}.
    """
    from configuracion.models import Parametro
    from automatizacion.models import RankingCliente, OfertaPropuesta
    # Deferred import para evitar circularidad a nivel de módulo
    from automatizacion.services import generar_combo_para_cliente

    now = timezone.now()
    periodo_conf = Parametro.get('RANKING_PERIODICIDAD', 'mensual')
    periodo_str = (
        now.strftime('%Y-%m')
        if periodo_conf != 'trimestral'
        else f"{now.year}-Q{(now.month - 1) // 3 + 1}"
    )

    try:
        cadencia = int(Parametro.get('OFERTA_CADENCIA_MINIMA_DIAS', _CADENCIA_MINIMA_DIAS_DEFAULT))
    except Exception:
        cadencia = _CADENCIA_MINIMA_DIAS_DEFAULT

    hoy = now.date()

    generadas = 0
    for rc in RankingCliente.objects.select_related('cliente').iterator(chunk_size=500):
        cliente = rc.cliente
        if not getattr(cliente, 'activo', True):
            continue
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

        # Cadencia mínima: no enviar si la última oferta enviada fue hace menos de N días
        ultima_enviada = (
            OfertaPropuesta.objects
            .filter(cliente=cliente, estado='enviada')
            .order_by('-creada')
            .values_list('creada', flat=True)
            .first()
        )
        if ultima_enviada is not None:
            dias_desde_ultimo = (hoy - ultima_enviada.date()).days
            if dias_desde_ultimo < cadencia:
                continue

        # Evaluar reglas de contexto: rechazos consecutivos suprimen la oferta
        try:
            from core.ai_rules.rules_engine import evaluar_reglas
            rechazos = OfertaPropuesta.objects.filter(
                cliente=cliente, estado='rechazada'
            ).order_by('-creada').values_list('estado', flat=True)[:3]
            rechazos_consecutivos = len([r for r in rechazos if r == 'rechazada'])
            if rechazos_consecutivos >= 3:
                continue
        except Exception:
            pass

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

        oferta = OfertaPropuesta.objects.create(
            cliente=cliente,
            titulo=titulo,
            descripcion=descripcion,
            tipo=categoria['tipo'],
            estado='pendiente',
            periodo=periodo_str,
            score_al_generar=min(float(rc.score or 0), 100.0),
            parametros=parametros_oferta,
        )
        # Envio automatico solo si el email esta verificado
        if not getattr(cliente, 'email_verificado', False):
            generadas += 1
            continue
        try:
            from automatizacion.services import enviar_oferta_email
            from automatizacion.models import MensajeOferta
            oferta.estado = 'enviada'
            oferta.fecha_validacion = timezone.now()
            oferta.save(update_fields=['estado', 'fecha_validacion'])
            ok, err = enviar_oferta_email(oferta, force=True)
            MensajeOferta.objects.create(
                oferta=oferta,
                cliente=cliente,
                estado='enviado' if ok else 'fallido',
                detalle='Enviado automaticamente' if ok else f'Error: {err}',
            )
        except Exception:
            pass
        generadas += 1

    # Log de generacion automatica
    try:
        from automatizacion.models import AutomationLog
        AutomationLog.objects.create(
            evento='ofertas_generadas_auto',
            descripcion=f'{generadas} ofertas generadas automaticamente para el periodo {periodo_str}',
            datos={'generadas': generadas, 'periodo': periodo_str},
        )
    except Exception:
        pass
    return {'generadas': generadas, 'periodo': periodo_str}
