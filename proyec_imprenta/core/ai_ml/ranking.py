"""
PI-1 — Algoritmo multicriterio de ranking de clientes.

Punto único de entrada para el cálculo de scores.
Invocado por ClienteInteligenteEngine y por la tarea Celery
tarea_ranking_clientes (thin wrapper).

Correcciones respecto a la versión anterior en tasks.py:
- ofertas_aceptadas se lee de AccionCliente (ya no hardcodeado a 0).
- Modo demo (4 clientes fijos) eliminado del flujo de producción.
- Normalización global: los máximos históricos se persisten en Parametro
  para que un único cliente en la ventana no obtenga siempre score = 100.
"""
import logging
from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


def calcular_ranking_clientes() -> dict:
    """
    Calcula y persiste el score multicriterio de cada cliente activo en la
    ventana configurada.

    Retorna:
        {'actualizados': int, 'periodo': str}
    """
    from clientes.models import Cliente
    from configuracion.models import RecetaProducto, Parametro
    from automatizacion.models import RankingCliente, RankingHistorico, AccionCliente
    from pedidos.models import Pedido, LineaPedido
    from productos.models import ProductoInsumo

    periodo_conf = Parametro.get('RANKING_PERIODICIDAD', 'mensual')
    ventana_dias = int(Parametro.get('RANKING_VENTANA_DIAS', 90))
    umbral_precio_critico = float(Parametro.get('INSUMO_CRITICO_UMBRAL_PRECIO', 500.0))

    desde = timezone.now().date() - timedelta(days=ventana_dias)
    pedidos_qs = Pedido.objects.filter(fecha_pedido__gte=desde)
    agregados = list(
        pedidos_qs
        .values('cliente_id')
        .annotate(total=Sum('monto_total'), cantidad=Count('id'))
    )

    # score mínimo para clientes sin pedidos en la ventana
    score_sin_pedidos = float(Parametro.get('RANKING_SCORE_SIN_PEDIDOS', 5.0))

    # Productos que usan insumos críticos por precio
    productos_criticos = set(
        RecetaProducto.objects
        .filter(insumos__precio_unitario__gte=umbral_precio_critico)
        .values_list('producto_id', flat=True)
        .distinct()
    )

    # Costo unitario BOM por producto (para margen)
    lineas_qs = (
        LineaPedido.objects
        .filter(pedido__fecha_pedido__gte=desde)
        .select_related('pedido')
    )
    producto_ids = list(lineas_qs.values_list('producto_id', flat=True).distinct())
    costo_unitario_por_producto: dict = {}
    if producto_ids:
        bom = ProductoInsumo.objects.select_related('insumo').filter(producto_id__in=producto_ids)
        for pi in bom:
            pid = pi.producto_id
            costo_unitario_por_producto[pid] = (
                costo_unitario_por_producto.get(pid, 0.0)
                + float(pi.cantidad_por_unidad) * float(pi.insumo.precio_unitario or 0)
            )

    meses_ventana = max(1, ventana_dias // 30)

    # Mapa cliente → líneas de pedido
    lineas_por_cliente: dict = {}
    for linea in lineas_qs:
        lineas_por_cliente.setdefault(linea.pedido.cliente_id, []).append(linea)

    # Ofertas aceptadas reales desde AccionCliente (no hardcodeado a 0)
    aceptaciones_por_cliente: dict = dict(
        AccionCliente.objects
        .filter(tipo='aceptar')
        .values('cliente_id')
        .annotate(n=Count('id'))
        .values_list('cliente_id', 'n')
    )

    # Calcular métricas individuales por cliente
    cliente_metrics: dict = {}
    for a in agregados:
        cliente_id = a['cliente_id']
        total = float(a['total'] or 0)
        cant = int(a['cantidad'] or 0)
        freq = cant / meses_ventana
        crit_total = sum(
            float(linea.precio_unitario) * float(linea.cantidad)
            for linea in lineas_por_cliente.get(cliente_id, [])
            if linea.producto_id in productos_criticos
        )
        margin_total = 0.0
        for linea in lineas_por_cliente.get(cliente_id, []):
            costo_unit = float(costo_unitario_por_producto.get(linea.producto_id, 0.0))
            ingreso = float(linea.precio_unitario) * float(linea.cantidad)
            margin_total += max(0.0, ingreso - costo_unit * float(linea.cantidad))
        cliente_metrics[cliente_id] = {
            'total': total,
            'cant': cant,
            'freq': float(freq),
            'crit_total': float(crit_total),
            'margin_total': float(margin_total),
            'ofertas_aceptadas': aceptaciones_por_cliente.get(cliente_id, 0),
        }

    now = timezone.now()
    periodo_str = _periodo_str(periodo_conf, now)

    # Modelo ML opcional
    try:
        from core.ai_ml.valor_cliente import predecir_valor_cliente
    except Exception:
        predecir_valor_cliente = None

    actualizado_count = 0

    if cliente_metrics:
        # --- Normalización global (resistente a cohorte de un solo cliente) ---
        # Los máximos históricos se persisten en Parametro; crecen con cada ciclo
        # y nunca retroceden, de modo que un único cliente en la ventana no obtiene
        # siempre score = 100 independientemente de su comportamiento real.
        max_total = _actualizar_max_historico(
            'RANK_HIST_MAX_TOTAL', max(m['total'] for m in cliente_metrics.values())
        )
        max_cant = _actualizar_max_historico(
            'RANK_HIST_MAX_CANT', max(m['cant'] for m in cliente_metrics.values())
        )
        max_freq = _actualizar_max_historico(
            'RANK_HIST_MAX_FREQ', max(m['freq'] for m in cliente_metrics.values())
        )
        max_crit = _actualizar_max_historico(
            'RANK_HIST_MAX_CRIT', max(m['crit_total'] for m in cliente_metrics.values())
        )
        max_margin = _actualizar_max_historico(
            'RANK_HIST_MAX_MARGIN', max(m['margin_total'] for m in cliente_metrics.values())
        )

        # Pesos en porcentaje entero; deben sumar 100.
        # Defaults: valor_total=30, margen=25, cantidad=20, frecuencia=15, critico=10 → total=100
        peso_cant = float(Parametro.get('RANKING_PESO_CANTIDAD', 20)) / 100.0
        peso_valor = float(Parametro.get('RANKING_PESO_VALOR_TOTAL', 30)) / 100.0
        peso_freq = float(Parametro.get('RANKING_PESO_FRECUENCIA', 15)) / 100.0
        peso_crit = float(Parametro.get('RANKING_PESO_CONSUMO_CRITICO', 10)) / 100.0
        peso_margen = float(Parametro.get('RANKING_PESO_MARGEN', 25)) / 100.0
        peso_sum = max(0.0001, peso_cant + peso_valor + peso_freq + peso_crit + peso_margen)
        _clientes_scores = {}  # acumular para bulk update al final del loop

        for cliente_id, m in cliente_metrics.items():
            total_norm = m['total'] / max_total
            cant_norm = m['cant'] / max_cant
            freq_norm = m['freq'] / max_freq
            crit_norm = m['crit_total'] / max_crit
            margen_norm = m['margin_total'] / max_margin

            score_reglas = round(
                (
                    (peso_cant * cant_norm)
                    + (peso_valor * total_norm)
                    + (peso_freq * freq_norm)
                    + (peso_crit * crit_norm)
                    + (peso_margen * margen_norm)
                ) / peso_sum,
                4,
            ) * 100.0

            if predecir_valor_cliente:
                features = {
                    'total_compras': m['total'],
                    'frecuencia': m['freq'],
                    'margen': margen_norm,
                    'ofertas_aceptadas': m['ofertas_aceptadas'],
                }
                try:
                    score_ml = predecir_valor_cliente(features)
                    score = 0.5 * score_reglas + 0.5 * score_ml
                except Exception:
                    score = score_reglas
            else:
                score = score_reglas

            if m['cant'] > 0 and score < 10:
                score = 10.0
            score = round(min(score, 100.0), 2)

            RankingCliente.objects.update_or_create(
                cliente_id=cliente_id,
                defaults={'score': score},
            )
            _clientes_scores[cliente_id] = score

            previo = (
                RankingHistorico.objects
                .filter(cliente_id=cliente_id)
                .order_by('-generado')
                .first()
            )
            variacion = 0.0
            if previo and previo.periodo != periodo_str:
                variacion = round(score - float(previo.score), 4)

            RankingHistorico.objects.update_or_create(
                cliente_id=cliente_id,
                periodo=periodo_str,
                defaults={
                    'score': score,
                    'variacion': variacion,
                    'metricas': {
                        'total_norm': round(total_norm, 4),
                        'cant_norm': round(cant_norm, 4),
                        'freq_norm': round(freq_norm, 4),
                        'crit_norm': round(crit_norm, 4),
                        'margen_norm': round(margen_norm, 4),
                    },
                },
            )
            actualizado_count += 1

        # Bulk update puntaje_estrategico para todos los clientes con pedidos (una sola query)
        if _clientes_scores:
            from django.db.models import Case, When, Value, FloatField
            Cliente.objects.filter(id__in=_clientes_scores.keys()).update(
                puntaje_estrategico=Case(
                    *[When(id=cid, then=Value(float(s))) for cid, s in _clientes_scores.items()],
                    output_field=FloatField(),
                ),
                fecha_ultima_actualizacion=now,
            )

    # --- Clientes sin pedidos en la ventana ---
    # Se les asigna un score mínimo configurable (por defecto 5) para que
    # aparezcan en el ranking y no queden con datos obsoletos indefinidamente.
    ids_con_pedidos = set(cliente_metrics.keys())
    clientes_sin_pedidos = Cliente.objects.filter(estado='Activo').exclude(id__in=ids_con_pedidos)
    _ids_sin_pedidos = []
    for cliente in clientes_sin_pedidos.iterator(chunk_size=500):
        RankingCliente.objects.update_or_create(
            cliente_id=cliente.id,
            defaults={'score': score_sin_pedidos},
        )
        _ids_sin_pedidos.append(cliente.id)
        RankingHistorico.objects.update_or_create(
            cliente_id=cliente.id,
            periodo=periodo_str,
            defaults={
                'score': score_sin_pedidos,
                'variacion': 0.0,
                'metricas': {'sin_pedidos_en_ventana': True},
            },
        )
        actualizado_count += 1

    # Bulk update puntaje_estrategico para clientes sin pedidos (una sola query)
    if _ids_sin_pedidos:
        Cliente.objects.filter(id__in=_ids_sin_pedidos).update(
            puntaje_estrategico=score_sin_pedidos,
            fecha_ultima_actualizacion=now,
        )

    return {'actualizados': actualizado_count, 'periodo': periodo_str}


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _actualizar_max_historico(codigo: str, valor_cohort: float) -> float:
    """
    Devuelve el máximo entre el valor histórico guardado en Parametro y el
    máximo de la cohorte actual.  Si la cohorte supera al histórico, persiste
    el nuevo máximo para futuros ciclos.
    """
    from configuracion.models import Parametro
    stored = float(Parametro.get(codigo, 0) or 0)
    nuevo_max = max(stored, valor_cohort)
    if nuevo_max > stored:
        Parametro.set(codigo, nuevo_max, tipo=Parametro.TIPO_FLOAT)
    return nuevo_max or 1.0


def _periodo_str(periodo_conf: str, now=None) -> str:
    if now is None:
        now = timezone.now()
    if periodo_conf == 'trimestral':
        q = (now.month - 1) // 3 + 1
        return f"{now.year}-Q{q}"
    return now.strftime('%Y-%m')
