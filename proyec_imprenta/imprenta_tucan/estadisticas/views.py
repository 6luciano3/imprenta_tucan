from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from datetime import timedelta
import statistics as stats_lib

from pedidos.models import Pedido, LineaPedido
from productos.models import Producto
from clientes.models import Cliente
from insumos.models import Insumo
from presupuestos.models import Presupuesto, PresupuestoDetalle
from proveedores.models import Proveedor


def _get_date_range(request):
    desde = parse_date(request.GET.get("desde") or "")
    hasta = parse_date(request.GET.get("hasta") or "")
    return desde, hasta


def _calc_stats(valores):
    if not valores:
        return None
    n = len(valores)
    vs = sorted(valores)
    media = sum(valores) / n
    mediana = stats_lib.median(valores)
    try:
        moda = stats_lib.mode(valores)
    except stats_lib.StatisticsError:
        moda = None
    desv_std = stats_lib.stdev(valores) if n > 1 else 0
    varianza = stats_lib.variance(valores) if n > 1 else 0
    rango = max(valores) - min(valores)

    def pct(data, p):
        idx = (len(data) - 1) * p / 100
        lo = int(idx)
        hi = lo + 1
        if hi >= len(data):
            return data[lo]
        return data[lo] + (idx - lo) * (data[hi] - data[lo])

    q1 = pct(vs, 25); q2 = pct(vs, 50); q3 = pct(vs, 75)
    p10 = pct(vs, 10); p90 = pct(vs, 90)

    if rango > 0:
        n_bins = min(10, n)
        bin_size = rango / n_bins
        bins = []
        for i in range(n_bins):
            lo = min(valores) + i * bin_size
            hi = lo + bin_size
            cnt = sum(1 for v in valores if lo <= v < hi)
            bins.append({"label": f"{lo:.1f}-{hi:.1f}", "count": cnt})
        bins[-1]["count"] += sum(1 for v in valores if v == max(valores))
    else:
        bins = [{"label": str(round(media, 2)), "count": n}]

    return {
        "n": n, "media": round(media, 2), "mediana": round(mediana, 2),
        "moda": round(moda, 2) if moda is not None else None,
        "desv_std": round(desv_std, 2), "varianza": round(varianza, 2),
        "rango": round(rango, 2), "minimo": round(min(valores), 2),
        "maximo": round(max(valores), 2),
        "q1": round(q1, 2), "q2": round(q2, 2), "q3": round(q3, 2),
        "p10": round(p10, 2), "p90": round(p90, 2),
        "iqr": round(q3 - q1, 2), "histograma": bins,
    }


def dashboard_estadisticas(request):
    modulos = [
        {"key": "clientes",     "label": "Clientes"},
        {"key": "pedidos",      "label": "Pedidos"},
        {"key": "productos",    "label": "Productos"},
        {"key": "insumos",      "label": "Insumos"},
        {"key": "presupuestos", "label": "Presupuestos"},
        {"key": "proveedores",  "label": "Proveedores"},
        {"key": "compras",      "label": "Compras"},
    ]
    return render(request, "estadisticas/dashboard.html", {"modulos": modulos})


def api_kpis(request):
    desde, hasta = _get_date_range(request)
    qs = Pedido.objects.all()
    if desde: qs = qs.filter(fecha_pedido__gte=desde)
    if hasta: qs = qs.filter(fecha_pedido__lte=hasta)
    ingresos = qs.aggregate(total=Sum("monto_total"))["total"] or 0
    hoy = timezone.now().date()
    return JsonResponse({
        "clientes": Cliente.objects.count(),
        "productos": Producto.objects.count(),
        "pedidos": Pedido.objects.count(),
        "ingresos_totales": float(ingresos),
        "pedidos_hoy": qs.filter(fecha_pedido=hoy).count(),
        "pedidos_semana": qs.filter(fecha_pedido__gte=hoy - timedelta(days=hoy.weekday())).count(),
        "pedidos_mes": qs.filter(fecha_pedido__gte=hoy.replace(day=1)).count(),
    })


def api_pedidos_por_estado(request):
    desde, hasta = _get_date_range(request)
    qs = Pedido.objects.all()
    if desde: qs = qs.filter(fecha_pedido__gte=desde)
    if hasta: qs = qs.filter(fecha_pedido__lte=hasta)
    data = qs.values("estado__nombre").annotate(n=Count("id")).order_by("estado__nombre")
    return JsonResponse({"labels": [d["estado__nombre"] or "Sin estado" for d in data], "values": [d["n"] for d in data]})


def api_ingresos_por_mes(request):
    hoy = timezone.now().date()
    desde, hasta = _get_date_range(request)
    qs = Pedido.objects.all()
    if not desde and not hasta: desde = hoy - timedelta(days=186)
    if desde: qs = qs.filter(fecha_pedido__gte=desde)
    if hasta: qs = qs.filter(fecha_pedido__lte=hasta)
    data = qs.annotate(mes=TruncMonth("fecha_pedido")).values("mes").annotate(total=Sum("monto_total")).order_by("mes")
    return JsonResponse({"labels": [d["mes"].strftime("%Y-%m") if d["mes"] else "N/A" for d in data], "values": [float(d["total"] or 0) for d in data]})


def api_top_productos(request):
    desde, hasta = _get_date_range(request)
    qs = LineaPedido.objects.all()
    if desde: qs = qs.filter(pedido__fecha_pedido__gte=desde)
    if hasta: qs = qs.filter(pedido__fecha_pedido__lte=hasta)
    data = qs.values("producto__nombreProducto").annotate(total=Sum("precio_unitario")).order_by("-total")[:5]
    return JsonResponse({"labels": [d["producto__nombreProducto"] or "Desconocido" for d in data], "values": [float(d["total"] or 0) for d in data]})


def api_top_clientes_score(request):
    try:
        from automatizacion.models import RankingCliente
    except ImportError:
        return JsonResponse({"error": "modulo automatizacion no disponible"}, status=500)
    n = int(request.GET.get("n", 10))
    qs = RankingCliente.objects.select_related("cliente").order_by("-score")[:n]
    TIERS = [("Premium", 90), ("Estrategico", 60), ("Estandar", 30), ("Nuevo", 0)]
    def _tier(s):
        for nombre, minimo in TIERS:
            if s >= minimo: return nombre
        return "Nuevo"
    return JsonResponse({"clientes": [{"id": rc.cliente_id, "nombre": str(rc.cliente), "score": round(float(rc.score), 1), "tier": _tier(float(rc.score))} for rc in qs]})


def api_insumos_urgentes(request):
    from django.core.cache import cache
    try:
        from core.motor.demanda_engine import DemandaInteligenteEngine
        if request.GET.get("refresh"): cache.delete("insumos_urgentes_resultado")
        resultado = cache.get("insumos_urgentes_resultado")
        if resultado is None:
            resultado = DemandaInteligenteEngine().ejecutar()
            cache.set("insumos_urgentes_resultado", resultado, 120)
        urgentes = [a for a in resultado.get("detalle", []) if a.get("prioridad") in ("alta", "critica")]
    except Exception as e:
        return JsonResponse({"error": str(e), "urgentes": []}, status=500)
    return JsonResponse({"urgentes": urgentes, "total_insumos_procesados": resultado.get("insumos_procesados", 0), "total_acciones": resultado.get("acciones_sugeridas", 0), "periodo": resultado.get("periodo", "")})


def api_proyeccion_demanda(request):
    try:
        from insumos.models import ProyeccionInsumo, predecir_demanda_media_movil
        from pedidos.models import OrdenCompra
        from django.db.models.functions import TruncMonth
        from core.motor.config import MotorConfig
        from core.motor.demanda_engine import DemandaInteligenteEngine
        n = int(request.GET.get("n", MotorConfig.get("PROYECCION_N_INSUMOS", cast=int) or 8))
        meses = int(request.GET.get("meses", MotorConfig.get("PROYECCION_MESES", cast=int) or 3))
    except Exception as e:
        return JsonResponse({"error": str(e), "proyecciones": []}, status=500)
    try:
        hoy = timezone.now()
        periodo_actual = hoy.strftime("%Y-%m")
        engine = DemandaInteligenteEngine()
        proyecciones_bd = {p.insumo_id: p.cantidad_proyectada for p in ProyeccionInsumo.objects.filter(periodo=periodo_actual)}
        hace_6m = hoy - timedelta(days=180)
        ordenes_por_insumo = {r["insumo_id"]: r["total"] for r in OrdenCompra.objects.filter(fecha_creacion__gte=hace_6m).values("insumo_id").annotate(total=Sum("cantidad"))}
        meses_activos = {}
        for r in OrdenCompra.objects.filter(fecha_creacion__gte=hace_6m).annotate(mes=TruncMonth("fecha_creacion")).values("insumo_id", "mes").distinct():
            meses_activos[r["insumo_id"]] = meses_activos.get(r["insumo_id"], 0) + 1
        ord_prom = {iid: total / meses_activos.get(iid, 1) for iid, total in ordenes_por_insumo.items()}
        insumos = (list(Insumo.objects.filter(activo=True, tipo=Insumo.TIPO_DIRECTO, idInsumo__in=proyecciones_bd.keys())) + list(Insumo.objects.filter(activo=True, tipo=Insumo.TIPO_DIRECTO).exclude(idInsumo__in=proyecciones_bd.keys()).order_by("stock")[:n*2]))[:n*3]
        proyecciones = []
        for ins in insumos:
            fuente = "catalogo"
            demanda = proyecciones_bd.get(ins.idInsumo)
            if demanda is not None: fuente = "proyeccion"
            if demanda is None:
                demanda = predecir_demanda_media_movil(ins, periodo_actual, meses=meses)
                if demanda and demanda > 0: fuente = "media_movil"
            if not demanda:
                prom = ord_prom.get(ins.idInsumo)
                if prom: demanda = prom; fuente = "ordenes"
            if not demanda:
                demanda = float(ins.cantidad or 0)
                if demanda > 0: fuente = "catalogo"
            if not demanda:
                demanda = float(ins.stock_minimo_manual or 0)
                if demanda > 0: fuente = "stock_minimo"
            demanda = float(demanda or 0)
            if fuente != "proyeccion" and demanda > 0:
                demanda = max(0.0, demanda * engine._factor_estacional(ins, hoy.month))
            if fuente in ("ordenes", "catalogo", "stock_minimo"):
                demanda = min(demanda, max(float(ins.stock_minimo_sugerido or 0)*10, float(ins.stock or 0)*5, 50.0))
            proyecciones.append({"insumo_id": ins.idInsumo, "nombre": ins.nombre, "codigo": ins.codigo, "stock_actual": float(ins.stock or 0), "stock_minimo": float(ins.stock_minimo_sugerido or 0), "demanda_proyectada": round(demanda, 1), "diferencia": round(float(ins.stock or 0) - demanda, 1), "fuente": fuente})
        proyecciones.sort(key=lambda x: x["diferencia"])
        return JsonResponse({"proyecciones": proyecciones[:n], "periodo": periodo_actual, "ventana_meses": meses})
    except Exception as e:
        return JsonResponse({"error": str(e), "proyecciones": []}, status=500)


def api_resumen_inteligencia(request):
    try:
        from automatizacion.models import RankingCliente, ScoreProveedor, CompraPropuesta, OfertaPropuesta
        from django.conf import settings
        import os
        tc = RankingCliente.objects.count()
        sp = (RankingCliente.objects.aggregate(avg=Sum("score"))["avg"] or 0) / tc if tc else 0
        mp = ScoreProveedor.objects.select_related("proveedor").order_by("-score").first()
        def _ml(f): return os.path.exists(os.path.normpath(os.path.join(settings.BASE_DIR, "..", "core", "ai_ml", f)))
        return JsonResponse({
            "motor_clientes": {"clientes_rankeados": tc, "score_promedio": round(sp, 1), "ofertas_pendientes": OfertaPropuesta.objects.filter(estado="pendiente").count(), "ofertas_enviadas": OfertaPropuesta.objects.filter(estado="enviada").count(), "ml_activo": _ml("modelo_valor_cliente.pkl")},
            "motor_proveedores": {"proveedores_rankeados": ScoreProveedor.objects.count(), "mejor_proveedor": str(mp.proveedor) if mp else None, "mejor_score": round(float(mp.score), 1) if mp else None, "ml_activo": _ml("modelo_score_proveedor.pkl")},
            "motor_insumos": {"sin_stock": Insumo.objects.filter(activo=True, stock=0).count(), "bajo_minimo": sum(1 for i in Insumo.objects.filter(activo=True, stock__gt=0) if i.stock < i.stock_minimo_sugerido), "propuestas_compra_pendientes": CompraPropuesta.objects.filter(estado="pendiente").count(), "ml_activo": _ml("modelo_demanda_insumo.pkl")},
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ── Estadistica Descriptiva ────────────────────────────────────────────────────

def api_estadistica_clientes(request):
    desde, hasta = _get_date_range(request)
    qs = Cliente.objects.all()
    if desde: qs = qs.filter(fecha_ultima_actualizacion__date__gte=desde)
    if hasta: qs = qs.filter(fecha_ultima_actualizacion__date__lte=hasta)
    scores = [float(s) for s in qs.values_list("puntaje_estrategico", flat=True) if s is not None]
    por_tipo = list(qs.values("tipo_cliente").annotate(n=Count("id")).order_by("-n"))
    por_estado = list(qs.values("estado").annotate(n=Count("id")))
    return JsonResponse({
        "variables": {"puntaje_estrategico": {"label": "Puntaje Estrategico", "stats": _calc_stats(scores)}},
        "categoricas": {
            "por_tipo_cliente": {"labels": [d["tipo_cliente"] for d in por_tipo], "values": [d["n"] for d in por_tipo]},
            "por_estado": {"labels": [d["estado"] for d in por_estado], "values": [d["n"] for d in por_estado]},
        }
    })


def api_estadistica_pedidos(request):
    desde, hasta = _get_date_range(request)
    qs = Pedido.objects.all()
    if desde: qs = qs.filter(fecha_pedido__gte=desde)
    if hasta: qs = qs.filter(fecha_pedido__lte=hasta)
    montos = [float(v) for v in qs.values_list("monto_total", flat=True) if v is not None]
    descuentos = [float(v) for v in qs.values_list("descuento", flat=True) if v is not None]
    por_estado = list(qs.values("estado__nombre").annotate(n=Count("id")).order_by("-n"))
    por_mes = list(qs.annotate(mes=TruncMonth("fecha_pedido")).values("mes").annotate(n=Count("id")).order_by("mes"))
    return JsonResponse({
        "variables": {
            "monto_total": {"label": "Monto Total ($)", "stats": _calc_stats(montos)},
            "descuento": {"label": "Descuento (%)", "stats": _calc_stats(descuentos)},
        },
        "categoricas": {
            "por_estado": {"labels": [d["estado__nombre"] or "Sin estado" for d in por_estado], "values": [d["n"] for d in por_estado]},
            "pedidos_por_mes": {"labels": [d["mes"].strftime("%Y-%m") if d["mes"] else "N/A" for d in por_mes], "values": [d["n"] for d in por_mes]},
        }
    })


def api_estadistica_productos(request):
    desde, hasta = _get_date_range(request)
    qs = Producto.objects.filter(activo=True)
    precios = [float(v) for v in qs.values_list("precioUnitario", flat=True) if v is not None]
    por_cat = list(qs.values("categoriaProducto__nombreCategoria").annotate(n=Count("idProducto")).order_by("-n"))
    por_tipo = list(qs.values("tipoProducto__nombreTipoProducto").annotate(n=Count("idProducto")).order_by("-n"))
    return JsonResponse({
        "variables": {"precio_unitario": {"label": "Precio Unitario ($)", "stats": _calc_stats(precios)}},
        "categoricas": {
            "por_categoria": {"labels": [d["categoriaProducto__nombreCategoria"] or "Sin categoria" for d in por_cat], "values": [d["n"] for d in por_cat]},
            "por_tipo": {"labels": [d["tipoProducto__nombreTipoProducto"] or "Sin tipo" for d in por_tipo], "values": [d["n"] for d in por_tipo]},
        }
    })


def api_estadistica_insumos(request):
    desde, hasta = _get_date_range(request)
    qs = Insumo.objects.filter(activo=True)
    if desde: qs = qs.filter(created_at__date__gte=desde)
    if hasta: qs = qs.filter(created_at__date__lte=hasta)
    stocks = [float(v) for v in qs.values_list("stock", flat=True) if v is not None]
    precios = [float(v) for v in qs.values_list("precio_unitario", flat=True) if v is not None and float(v) > 0]
    por_cat = list(qs.values("categoria").annotate(n=Count("idInsumo")).order_by("-n")[:10])
    por_tipo = list(qs.values("tipo").annotate(n=Count("idInsumo")))
    return JsonResponse({
        "variables": {
            "stock": {"label": "Stock Actual (unidades)", "stats": _calc_stats(stocks)},
            "precio_unitario": {"label": "Precio Unitario ($)", "stats": _calc_stats(precios)},
        },
        "categoricas": {
            "por_categoria": {"labels": [d["categoria"] or "Sin categoria" for d in por_cat], "values": [d["n"] for d in por_cat]},
            "por_tipo": {"labels": [d["tipo"] for d in por_tipo], "values": [d["n"] for d in por_tipo]},
        }
    })


def api_estadistica_presupuestos(request):
    desde, hasta = _get_date_range(request)
    pqs = Presupuesto.objects.all()
    if desde: pqs = pqs.filter(fecha__gte=desde)
    if hasta: pqs = pqs.filter(fecha__lte=hasta)
    totales = [float(v) for v in pqs.values_list("total", flat=True) if v is not None]
    dqs = PresupuestoDetalle.objects.filter(presupuesto__in=pqs)
    cantidades = [float(v) for v in dqs.values_list("cantidad", flat=True) if v is not None]
    precios = [float(v) for v in dqs.values_list("precio_unitario", flat=True) if v is not None]
    descuentos = [float(v) for v in dqs.values_list("descuento", flat=True) if v is not None]
    por_respuesta = list(pqs.values("respuesta_cliente").annotate(n=Count("id")))
    por_estado = list(pqs.values("estado").annotate(n=Count("id")))
    return JsonResponse({
        "variables": {
            "total": {"label": "Total Presupuesto ($)", "stats": _calc_stats(totales)},
            "cantidad_linea": {"label": "Cantidad por Linea", "stats": _calc_stats(cantidades)},
            "precio_unitario": {"label": "Precio Unitario ($)", "stats": _calc_stats(precios)},
            "descuento": {"label": "Descuento (%)", "stats": _calc_stats(descuentos)},
        },
        "categoricas": {
            "por_respuesta": {"labels": [d["respuesta_cliente"] for d in por_respuesta], "values": [d["n"] for d in por_respuesta]},
            "por_estado": {"labels": [d["estado"] for d in por_estado], "values": [d["n"] for d in por_estado]},
        }
    })


def api_estadistica_proveedores(request):
    desde, hasta = _get_date_range(request)
    pvqs = Proveedor.objects.filter(activo=True)
    if desde: pvqs = pvqs.filter(fecha_creacion__date__gte=desde)
    if hasta: pvqs = pvqs.filter(fecha_creacion__date__lte=hasta)
    por_rubro = list(pvqs.values("rubro").annotate(n=Count("id")).order_by("-n")[:10])
    insumos_por_prov = list(Insumo.objects.filter(activo=True, proveedor__isnull=False).values("proveedor__nombre").annotate(n=Count("idInsumo")).order_by("-n")[:10])
    n_insumos = [d["n"] for d in insumos_por_prov]
    return JsonResponse({
        "variables": {"insumos_por_proveedor": {"label": "Insumos por Proveedor", "stats": _calc_stats(n_insumos)}},
        "categoricas": {
            "por_rubro": {"labels": [d["rubro"] or "Sin rubro" for d in por_rubro], "values": [d["n"] for d in por_rubro]},
            "activos_vs_inactivos": {"labels": ["Activo", "Inactivo"], "values": [pvqs.filter(activo=True).count(), Proveedor.objects.filter(activo=False).count()]},
            "insumos_por_proveedor": {"labels": [d["proveedor__nombre"] for d in insumos_por_prov], "values": [d["n"] for d in insumos_por_prov]},
        }
    })


def api_estadistica_compras(request):
    desde, hasta = _get_date_range(request)
    from pedidos.models import OrdenCompra
    qs = OrdenCompra.objects.all()
    if desde: qs = qs.filter(fecha_creacion__date__gte=desde)
    if hasta: qs = qs.filter(fecha_creacion__date__lte=hasta)
    cantidades = [float(v) for v in qs.values_list("cantidad", flat=True) if v is not None]
    por_estado = list(qs.values("estado").annotate(n=Count("id")).order_by("-n"))
    por_prov = list(qs.values("proveedor__nombre").annotate(n=Count("id")).order_by("-n")[:10])
    por_mes = list(qs.annotate(mes=TruncMonth("fecha_creacion")).values("mes").annotate(n=Count("id")).order_by("mes"))
    return JsonResponse({
        "variables": {"cantidad": {"label": "Cantidad por Orden", "stats": _calc_stats(cantidades)}},
        "categoricas": {
            "por_estado": {"labels": [d["estado"] for d in por_estado], "values": [d["n"] for d in por_estado]},
            "por_proveedor": {"labels": [d["proveedor__nombre"] or "Sin proveedor" for d in por_prov], "values": [d["n"] for d in por_prov]},
            "ordenes_por_mes": {"labels": [d["mes"].strftime("%Y-%m") if d["mes"] else "N/A" for d in por_mes], "values": [d["n"] for d in por_mes]},
        }
    })


# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES COMUNES PARA INFORMES PDF
# ═══════════════════════════════════════════════════════════════════════════════



# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES DE GRAFICOS CON MATPLOTLIB
# ═══════════════════════════════════════════════════════════════════════════════

def _grafico_barras(labels, values, titulo, color="#1E3A5F", ancho=14, alto=4):
    """Genera un grafico de barras y retorna un ImageReader para ReportLab."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from io import BytesIO
    fig, ax = plt.subplots(figsize=(ancho, alto))
    bars = ax.bar(labels, values, color=color, edgecolor="white", linewidth=0.5)
    ax.set_title(titulo, fontsize=11, fontweight="bold", pad=10, color="#1E3A5F")
    ax.set_xlabel("")
    ax.tick_params(axis="x", rotation=30, labelsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.01,
                f"{val:,.0f}", ha="center", va="bottom", fontsize=7, color="#2C3E50")
    plt.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _grafico_torta(labels, values, titulo, ancho=6, alto=4):
    """Genera un grafico de torta y retorna un ImageReader para ReportLab."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from io import BytesIO
    COLORS = ["#1E3A5F","#2980B9","#27AE60","#F39C12","#E74C3C","#9B59B6","#1ABC9C","#E67E22"]
    fig, ax = plt.subplots(figsize=(ancho, alto))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, autopct="%1.1f%%",
        colors=COLORS[:len(labels)], startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5}
    )
    for t in texts: t.set_fontsize(8)
    for at in autotexts: at.set_fontsize(7); at.set_color("white"); at.set_fontweight("bold")
    ax.set_title(titulo, fontsize=11, fontweight="bold", pad=10, color="#1E3A5F")
    plt.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _grafico_linea(labels, values, titulo, color="#2980B9", ancho=14, alto=4):
    """Genera un grafico de linea y retorna un ImageReader para ReportLab."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from io import BytesIO
    fig, ax = plt.subplots(figsize=(ancho, alto))
    ax.plot(labels, values, color=color, linewidth=2, marker="o", markersize=5, markerfacecolor="white", markeredgewidth=2)
    ax.fill_between(range(len(labels)), values, alpha=0.1, color=color)
    ax.set_title(titulo, fontsize=11, fontweight="bold", pad=10, color="#1E3A5F")
    ax.tick_params(axis="x", rotation=30, labelsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    plt.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _img_flowable(buf, ancho_cm, alto_cm):
    """Convierte un BytesIO de imagen a un flowable de ReportLab."""
    from reportlab.platypus import Image as RLImage
    from reportlab.lib.units import cm
    buf.seek(0)
    return RLImage(buf, width=ancho_cm*cm, height=alto_cm*cm)


def _pdf_setup(titulo_informe, request):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
    from io import BytesIO
    from django.utils import timezone

    buffer = BytesIO()
    W, H = A4
    content_width = W - 4*cm
    hoy = timezone.now().date()

    COLOR_AZUL       = colors.HexColor("#1E3A5F")
    COLOR_AZUL_CLARO = colors.HexColor("#D6E4F0")
    COLOR_GRIS       = colors.HexColor("#F4F6F8")
    COLOR_TEXTO      = colors.HexColor("#2C3E50")
    COLOR_BORDE      = colors.HexColor("#BDC3C7")

    st = {
        "titulo":     ParagraphStyle("t1", fontSize=18, fontName="Helvetica-Bold",
                          textColor=COLOR_AZUL, alignment=TA_RIGHT, spaceAfter=2),
        "sub":        ParagraphStyle("t2", fontSize=8, fontName="Helvetica",
                          textColor=COLOR_TEXTO, alignment=TA_RIGHT, spaceAfter=1),
        "seccion":    ParagraphStyle("t3", fontSize=11, fontName="Helvetica-Bold",
                          textColor=COLOR_AZUL, spaceBefore=14, spaceAfter=5),
        "normal":     ParagraphStyle("t4", fontSize=8, fontName="Helvetica",
                          textColor=COLOR_TEXTO, leading=12),
        "bold":       ParagraphStyle("t5", fontSize=8, fontName="Helvetica-Bold",
                          textColor=COLOR_TEXTO),
        "right":      ParagraphStyle("t6", fontSize=8, fontName="Helvetica",
                          textColor=COLOR_TEXTO, alignment=TA_RIGHT),
        "right_bold": ParagraphStyle("t7", fontSize=8, fontName="Helvetica-Bold",
                          textColor=COLOR_TEXTO, alignment=TA_RIGHT),
        "footer":     ParagraphStyle("t8", fontSize=7, fontName="Helvetica",
                          textColor=colors.gray, alignment=TA_CENTER),
        "azul":       COLOR_AZUL,
        "azul_claro": COLOR_AZUL_CLARO,
        "gris":       COLOR_GRIS,
        "texto":      COLOR_TEXTO,
        "borde":      COLOR_BORDE,
        "cw":         content_width,
        "cm":         cm,
        "hoy":        hoy,
        "titulo_inf": titulo_informe,
    }

    def _draw_page(canvas_obj, doc_obj):
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib import colors as _c
        _W, _H = _A4
        canvas_obj.saveState()
        canvas_obj.setFillColor(_c.HexColor("#F4F6F8"))
        canvas_obj.rect(0, 0, _W, 1.2*cm, fill=1, stroke=0)
        canvas_obj.setStrokeColor(_c.HexColor("#BDC3C7"))
        canvas_obj.line(0, 1.2*cm, _W, 1.2*cm)
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(_c.HexColor("#7F8C8D"))
        canvas_obj.drawString(2*cm, 0.42*cm,
            "Sistema de Gestion - Imprenta Tucan  |  " + hoy.strftime("%d/%m/%Y"))
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.setFillColor(_c.HexColor("#1E3A5F"))
        canvas_obj.drawRightString(_W - 2*cm, 0.42*cm,
            "Pagina " + str(doc_obj.page))
        canvas_obj.restoreState()

    frame = Frame(
        2*cm, 1.5*cm, content_width, H - 3*cm,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="main"
    )
    template = PageTemplate(id="main", frames=[frame], onPage=_draw_page)
    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        pageTemplates=[template],
        title=titulo_informe + " - Imprenta Tucan",
    )
    return buffer, doc, st, content_width


def _pdf_header(st, titulo_informe, periodo_str, usuario_nombre):
    from reportlab.platypus import Table, TableStyle, Image, Paragraph, HRFlowable
    from reportlab.lib import colors
    from django.utils import timezone
    import os
    hoy = timezone.now().date()
    cm = st["cm"]
    cw = st["cw"]
    logo_path = os.path.join("static", "img", "Logo Tucan_Mesa de trabajo 1.png")
    logo_cell = Image(logo_path, width=5.46*cm, height=2.5*cm) if os.path.exists(logo_path) else Paragraph("<b>IMPRENTA TUCAN</b>", st["titulo"])
    header_inner = Table([
        [Paragraph(titulo_informe.upper(), st["titulo"])],
        [Paragraph(f"<b>Fecha:</b> {hoy.strftime('%d/%m/%Y')}", st["sub"])],
        [Paragraph(f"<b>Periodo:</b> {periodo_str}", st["sub"])],
        [Paragraph(f"<b>Generado por:</b> {usuario_nombre}", st["sub"])],
    ], colWidths=[cw - 5.46*cm])
    hdr = Table([[logo_cell, header_inner]], colWidths=[5.46*cm, cw - 5.46*cm])
    hdr.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    hr = HRFlowable(width="100%", thickness=2, color=st["azul"], spaceAfter=10)
    return hdr, hr


def _tbl_style(st, header_cols=None):
    from reportlab.platypus import TableStyle
    from reportlab.lib import colors
    base = [
        ("BACKGROUND", (0,0), (-1,0), colors.white),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.HexColor("#1E3A5F")),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,0), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#F8F9FA"), colors.white]),
        ("GRID",   (0,0), (-1,-1), 0.5, colors.HexColor("#DEE2E6")),
        ("LINEBELOW", (0,0), (-1,0), 1.5, colors.HexColor("#1E3A5F")),
        ("LINEABOVE", (0,0), (-1,0), 1.5, colors.HexColor("#1E3A5F")),
        ("PADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,0), 8),
        ("BOTTOMPADDING", (0,0), (-1,0), 8),
        ("VALIGN",  (0,0), (-1,-1), "MIDDLE"),
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,1), (-1,-1), 8),
    ]
    return TableStyle(base)


def _pdf_firma(st, usuario_nombre):
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, HRFlowable
    from django.utils import timezone
    hoy = timezone.now().date()
    cm = st["cm"]; cw = st["cw"]
    hr = HRFlowable(width="100%", thickness=1, color=st["azul"], spaceAfter=6, spaceBefore=16)
    firma = Table([[
        Table([[Paragraph("<b>Aprobado por:</b>", st["bold"])],[Spacer(1,0.4*cm)],[Paragraph(f"<b>{usuario_nombre}</b>", st["bold"])],[Paragraph("_"*28, st["normal"])],[Paragraph("Firma: _________________", st["normal"])]]),
        Table([[Paragraph(f"Generado: {hoy.strftime('%d/%m/%Y')}", st["sub"])],[Paragraph("Imprenta Tucan - Sistema de Gestion", st["footer"])]])
    ]], colWidths=[cw*0.5, cw*0.5])
    firma.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"BOTTOM"),("ALIGN",(1,0),(1,0),"RIGHT")]))
    return hr, firma


def _pdf_response(buffer, nombre_archivo, request=None):
    from django.http import HttpResponse
    from django.utils import timezone
    buffer.seek(0)
    hoy = timezone.now().date()
    download = (request.GET.get("download", "0") == "1") if request else False
    disposition = "attachment" if download else "inline"
    resp = HttpResponse(buffer, content_type="application/pdf")
    resp["Content-Disposition"] = (disposition + '; filename="' +
        nombre_archivo + '_' + hoy.strftime("%Y%m%d") + '.pdf"')
    return resp


def _periodo_str(desde, hasta):
    from django.utils import timezone
    hoy = timezone.now().date()
    if desde and hasta: return f"{desde.strftime('%d/%m/%Y')} - {hasta.strftime('%d/%m/%Y')}"
    if desde: return f"Desde {desde.strftime('%d/%m/%Y')}"
    if hasta: return f"Hasta {hasta.strftime('%d/%m/%Y')}"
    return f"Al {hoy.strftime('%d/%m/%Y')}"


# ═══════════════════════════════════════════════════════════════════════════════
# INFORME 1: PEDIDOS
# ═══════════════════════════════════════════════════════════════════════════════
from django.contrib.auth.decorators import login_required

@login_required
def informe_pdf_pedidos(request):
    from reportlab.platypus import Paragraph, Spacer, Table, HRFlowable
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncMonth
    from django.utils.dateparse import parse_date
    desde = parse_date(request.GET.get("desde","") or "")
    hasta = parse_date(request.GET.get("hasta","") or "")
    usuario = str(request.user) if request.user.is_authenticated else "Sistema"
    buffer, doc, st, cw = _pdf_setup("Informe de Pedidos", request)
    qs = Pedido.objects.select_related("cliente","estado").all()
    if desde: qs = qs.filter(fecha_pedido__gte=desde)
    if hasta: qs = qs.filter(fecha_pedido__lte=hasta)
    story = []
    hdr, hr = _pdf_header(st, "Informe de Pedidos", _periodo_str(desde, hasta), usuario)
    story += [hdr, hr]
    # KPIs
    story.append(Paragraph("Resumen Ejecutivo", st["seccion"]))
    total = qs.count(); ingresos = qs.aggregate(t=Sum("monto_total"))["t"] or 0
    kpi_data = [
        [Paragraph("<b>Indicador</b>", st["bold"]), Paragraph("<b>Valor</b>", st["bold"])],
        [Paragraph("Total pedidos", st["normal"]), Paragraph(f"<b>{total}</b>", st["bold"])],
        [Paragraph("Ingresos totales", st["normal"]), Paragraph(f"<b>${float(ingresos):,.2f}</b>", st["bold"])],
        [Paragraph("Ticket promedio", st["normal"]), Paragraph(f"<b>${float(ingresos)/total:,.2f}</b>" if total else "-", st["bold"])],
    ]
    t = Table(kpi_data, colWidths=[cw*0.6, cw*0.4]); t.setStyle(_tbl_style(st)); story.append(t)
    # Por estado
    story.append(Paragraph("Pedidos por Estado", st["seccion"]))
    por_estado = qs.values("estado__nombre").annotate(n=Count("id"), total=Sum("monto_total")).order_by("-n")
    rows = [[Paragraph("<b>Estado</b>",st["bold"]), Paragraph("<b>Cantidad</b>",st["bold"]), Paragraph("<b>Ingresos</b>",st["bold"])]]
    for r in por_estado:
        rows.append([Paragraph(str(r["estado__nombre"] or "-"),st["normal"]), Paragraph(str(r["n"]),st["normal"]), Paragraph(f"${float(r['total'] or 0):,.2f}",st["normal"])])
    t2 = Table(rows, colWidths=[cw*0.5,cw*0.2,cw*0.3]); t2.setStyle(_tbl_style(st)); story.append(t2)
    # Listado reciente
    story.append(Paragraph("Ultimos 20 Pedidos", st["seccion"]))
    recientes = qs.order_by("-fecha_pedido")[:20]
    rows2 = [[Paragraph("<b>#</b>",st["bold"]),Paragraph("<b>Cliente</b>",st["bold"]),Paragraph("<b>Fecha</b>",st["bold"]),Paragraph("<b>Estado</b>",st["bold"]),Paragraph("<b>Total</b>",st["bold"])]]
    for p in recientes:
        rows2.append([Paragraph(str(p.id),st["normal"]),Paragraph(str(p.cliente)[:30],st["normal"]),Paragraph(p.fecha_pedido.strftime("%d/%m/%y"),st["normal"]),Paragraph(str(p.estado),st["normal"]),Paragraph(f"${float(p.monto_total):,.2f}",st["normal"])])
    t3 = Table(rows2, colWidths=[cw*0.08,cw*0.32,cw*0.15,cw*0.2,cw*0.25]); t3.setStyle(_tbl_style(st)); story.append(t3)
    # Grafico 1: Pedidos por estado (barras)
    story.append(Paragraph("Grafico: Pedidos por Estado", st["seccion"]))
    estados_labels = [str(r["estado__nombre"] or "Sin estado") for r in por_estado]
    estados_vals = [r["n"] for r in por_estado]
    if estados_labels:
        img = _grafico_barras(estados_labels, estados_vals, "Pedidos por Estado", "#1E3A5F")
        story.append(_img_flowable(img, 15, 5))
    # Grafico 2: Ingresos por mes (linea)
    from django.db.models.functions import TruncMonth
    ingresos_mes = qs.annotate(mes=TruncMonth("fecha_pedido")).values("mes").annotate(total=Sum("monto_total")).order_by("mes")
    mes_labels = [r["mes"].strftime("%b %Y") if r["mes"] else "N/A" for r in ingresos_mes]
    mes_vals = [float(r["total"] or 0) for r in ingresos_mes]
    if mes_labels:
        story.append(Paragraph("Grafico: Ingresos por Mes", st["seccion"]))
        img2 = _grafico_linea(mes_labels, mes_vals, "Ingresos por Mes ($)", "#2980B9")
        story.append(_img_flowable(img2, 15, 5))
    hr2, firma = _pdf_firma(st, usuario); story += [hr2, firma]
    # Dos pasadas para obtener total de paginas
    def _contar_paginas(story_items, doc_obj):
        from io import BytesIO as _BytesIO
        from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib.units import cm as _cm
        _W, _H = _A4
        _buf = _BytesIO()
        _frame = Frame(2*_cm, 1.5*_cm, _W-4*_cm, _H-3*_cm,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        _tpl = PageTemplate(id="cnt", frames=[_frame], onPage=lambda c,d: None)
        _doc2 = BaseDocTemplate(_buf, pagesize=_A4, pageTemplates=[_tpl])
        _doc2.build(story_items)
        _buf.seek(0)
        from pypdf import PdfReader as _PR
        return len(_PR(_buf).pages)

    import copy
    _total = _contar_paginas(copy.copy(story), doc)

    def _draw_page_nm(canvas_obj, doc_obj):
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib import colors as _c
        _W, _H = _A4
        canvas_obj.saveState()
        canvas_obj.setFillColor(_c.HexColor("#F4F6F8"))
        canvas_obj.rect(0, 0, _W, 1.2*st["cm"], fill=1, stroke=0)
        canvas_obj.setStrokeColor(_c.HexColor("#BDC3C7"))
        canvas_obj.line(0, 1.2*st["cm"], _W, 1.2*st["cm"])
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(_c.HexColor("#7F8C8D"))
        canvas_obj.drawString(2*st["cm"], 0.42*st["cm"],
            "Sistema de Gestion - Imprenta Tucan  |  " + st["hoy"].strftime("%d/%m/%Y"))
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.setFillColor(_c.HexColor("#1E3A5F"))
        canvas_obj.drawRightString(_W - 2*st["cm"], 0.42*st["cm"],
            "Pagina " + str(doc_obj.page) + " de " + str(_total))
        canvas_obj.restoreState()

    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
    from reportlab.lib.pagesizes import A4 as _A42
    from reportlab.lib.units import cm as _cm2
    _W2, _H2 = _A42
    _frame2 = Frame(2*_cm2, 1.5*_cm2, _W2-4*_cm2, _H2-3*_cm2,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="main")
    _tpl2 = PageTemplate(id="main", frames=[_frame2], onPage=_draw_page_nm)
    from io import BytesIO as _BytesIO2
    buffer = _BytesIO2()
    _doc_final = BaseDocTemplate(buffer, pagesize=_A42,
        pageTemplates=[_tpl2],
        title=st["titulo_inf"] + " - Imprenta Tucan")
    _doc_final.build(story)
    return _pdf_response(buffer, "informe_pedidos", request)


# ═══════════════════════════════════════════════════════════════════════════════
# INFORME 2: CLIENTES
# ═══════════════════════════════════════════════════════════════════════════════
@login_required
def informe_pdf_clientes(request):
    from reportlab.platypus import Paragraph, Spacer, Table, HRFlowable
    from django.db.models import Count, Sum, Avg
    from django.utils.dateparse import parse_date
    desde = parse_date(request.GET.get("desde","") or "")
    hasta = parse_date(request.GET.get("hasta","") or "")
    usuario = str(request.user) if request.user.is_authenticated else "Sistema"
    buffer, doc, st, cw = _pdf_setup("Informe de Clientes", request)
    story = []
    hdr, hr = _pdf_header(st, "Informe de Clientes", _periodo_str(desde, hasta), usuario)
    story += [hdr, hr]
    total_clientes = Cliente.objects.count()
    story.append(Paragraph("Resumen de Clientes", st["seccion"]))
    rows = [[Paragraph("<b>Indicador</b>",st["bold"]),Paragraph("<b>Valor</b>",st["bold"])],
            [Paragraph("Total clientes",st["normal"]),Paragraph(f"<b>{total_clientes}</b>",st["bold"])]]
    try:
        from automatizacion.models import RankingCliente
        premium = RankingCliente.objects.filter(score__gte=90).count()
        estrategico = RankingCliente.objects.filter(score__gte=60,score__lt=90).count()
        estandar = RankingCliente.objects.filter(score__gte=30,score__lt=60).count()
        nuevos = RankingCliente.objects.filter(score__lt=30).count()
        rows += [
            [Paragraph("Premium (>=90)",st["normal"]),Paragraph(f"<b>{premium}</b>",st["bold"])],
            [Paragraph("Estrategico (60-89)",st["normal"]),Paragraph(f"<b>{estrategico}</b>",st["bold"])],
            [Paragraph("Estandar (30-59)",st["normal"]),Paragraph(f"<b>{estandar}</b>",st["bold"])],
            [Paragraph("Nuevos (<30)",st["normal"]),Paragraph(f"<b>{nuevos}</b>",st["bold"])],
        ]
    except: pass
    t = Table(rows,colWidths=[cw*0.6,cw*0.4]); t.setStyle(_tbl_style(st)); story.append(t)
    # Top clientes por pedidos
    story.append(Paragraph("Top 15 Clientes por Pedidos", st["seccion"]))
    top = Cliente.objects.annotate(n_pedidos=Count("pedido"),total_ing=Sum("pedido__monto_total")).order_by("-n_pedidos")[:15]
    rows2 = [[Paragraph("<b>Cliente</b>",st["bold"]),Paragraph("<b>Tipo</b>",st["bold"]),Paragraph("<b>Pedidos</b>",st["bold"]),Paragraph("<b>Ingresos</b>",st["bold"])]]
    for c in top:
        rows2.append([Paragraph(str(c)[:35],st["normal"]),Paragraph(str(c.tipo_cliente or "-"),st["normal"]),Paragraph(str(c.n_pedidos),st["normal"]),Paragraph(f"${float(c.total_ing or 0):,.2f}",st["normal"])])
    t2 = Table(rows2,colWidths=[cw*0.4,cw*0.2,cw*0.15,cw*0.25]); t2.setStyle(_tbl_style(st)); story.append(t2)
    # Grafico: Top clientes por pedidos (barras)
    top_nombres = [str(c)[:20] for c in top]
    top_vals = [c.n_pedidos for c in top]
    if top_nombres:
        story.append(Paragraph("Grafico: Top Clientes por Pedidos", st["seccion"]))
        img = _grafico_barras(top_nombres, top_vals, "Top Clientes por Pedidos", "#27AE60")
        story.append(_img_flowable(img, 15, 5))
    # Grafico: por tipo de cliente (torta)
    tipo_qs = Cliente.objects.values("tipo_cliente").annotate(n=Count("id")).order_by("-n")
    tipo_labels = [str(r["tipo_cliente"] or "Sin tipo") for r in tipo_qs]
    tipo_vals = [r["n"] for r in tipo_qs]
    if tipo_labels:
        story.append(Paragraph("Grafico: Distribucion por Tipo de Cliente", st["seccion"]))
        img2 = _grafico_torta(tipo_labels, tipo_vals, "Clientes por Tipo")
        story.append(_img_flowable(img2, 9, 6))
    hr2, firma = _pdf_firma(st, usuario); story += [hr2, firma]
    # Dos pasadas para obtener total de paginas
    def _contar_paginas(story_items, doc_obj):
        from io import BytesIO as _BytesIO
        from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib.units import cm as _cm
        _W, _H = _A4
        _buf = _BytesIO()
        _frame = Frame(2*_cm, 1.5*_cm, _W-4*_cm, _H-3*_cm,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        _tpl = PageTemplate(id="cnt", frames=[_frame], onPage=lambda c,d: None)
        _doc2 = BaseDocTemplate(_buf, pagesize=_A4, pageTemplates=[_tpl])
        _doc2.build(story_items)
        _buf.seek(0)
        from pypdf import PdfReader as _PR
        return len(_PR(_buf).pages)

    import copy
    _total = _contar_paginas(copy.copy(story), doc)

    def _draw_page_nm(canvas_obj, doc_obj):
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib import colors as _c
        _W, _H = _A4
        canvas_obj.saveState()
        canvas_obj.setFillColor(_c.HexColor("#F4F6F8"))
        canvas_obj.rect(0, 0, _W, 1.2*st["cm"], fill=1, stroke=0)
        canvas_obj.setStrokeColor(_c.HexColor("#BDC3C7"))
        canvas_obj.line(0, 1.2*st["cm"], _W, 1.2*st["cm"])
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(_c.HexColor("#7F8C8D"))
        canvas_obj.drawString(2*st["cm"], 0.42*st["cm"],
            "Sistema de Gestion - Imprenta Tucan  |  " + st["hoy"].strftime("%d/%m/%Y"))
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.setFillColor(_c.HexColor("#1E3A5F"))
        canvas_obj.drawRightString(_W - 2*st["cm"], 0.42*st["cm"],
            "Pagina " + str(doc_obj.page) + " de " + str(_total))
        canvas_obj.restoreState()

    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
    from reportlab.lib.pagesizes import A4 as _A42
    from reportlab.lib.units import cm as _cm2
    _W2, _H2 = _A42
    _frame2 = Frame(2*_cm2, 1.5*_cm2, _W2-4*_cm2, _H2-3*_cm2,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="main")
    _tpl2 = PageTemplate(id="main", frames=[_frame2], onPage=_draw_page_nm)
    from io import BytesIO as _BytesIO2
    buffer = _BytesIO2()
    _doc_final = BaseDocTemplate(buffer, pagesize=_A42,
        pageTemplates=[_tpl2],
        title=st["titulo_inf"] + " - Imprenta Tucan")
    _doc_final.build(story)
    return _pdf_response(buffer, "informe_clientes", request)


# ═══════════════════════════════════════════════════════════════════════════════
# INFORME 3: PRODUCTOS
# ═══════════════════════════════════════════════════════════════════════════════
@login_required
def informe_pdf_productos(request):
    from reportlab.platypus import Paragraph, Table
    from django.db.models import Count, Sum
    from django.utils.dateparse import parse_date
    desde = parse_date(request.GET.get("desde","") or "")
    hasta = parse_date(request.GET.get("hasta","") or "")
    usuario = str(request.user) if request.user.is_authenticated else "Sistema"
    buffer, doc, st, cw = _pdf_setup("Informe de Productos", request)
    story = []
    hdr, hr = _pdf_header(st, "Informe de Productos", _periodo_str(desde, hasta), usuario)
    story += [hdr, hr]
    story.append(Paragraph("Resumen de Productos", st["seccion"]))
    total = Producto.objects.count()
    rows = [[Paragraph("<b>Indicador</b>",st["bold"]),Paragraph("<b>Valor</b>",st["bold"])],
            [Paragraph("Total productos",st["normal"]),Paragraph(f"<b>{total}</b>",st["bold"])]]
    t = Table(rows,colWidths=[cw*0.6,cw*0.4]); t.setStyle(_tbl_style(st)); story.append(t)
    story.append(Paragraph("Top Productos por Ventas", st["seccion"]))
    qs_lp = LineaPedido.objects.all()
    if desde: qs_lp = qs_lp.filter(pedido__fecha_pedido__gte=desde)
    if hasta: qs_lp = qs_lp.filter(pedido__fecha_pedido__lte=hasta)
    top = qs_lp.values("producto__nombreProducto","producto__categoria").annotate(veces=Count("id"),ingresos=Sum("precio_unitario")).order_by("-ingresos")[:20]
    rows2 = [[Paragraph("<b>#</b>",st["bold"]),Paragraph("<b>Producto</b>",st["bold"]),Paragraph("<b>Categoria</b>",st["bold"]),Paragraph("<b>Ventas</b>",st["bold"]),Paragraph("<b>Ingresos</b>",st["bold"])]]
    for i,r in enumerate(top,1):
        rows2.append([Paragraph(str(i),st["normal"]),Paragraph(str(r["producto__nombreProducto"] or "-")[:30],st["normal"]),Paragraph(str(r["producto__categoria"] or "-"),st["normal"]),Paragraph(str(r["veces"]),st["normal"]),Paragraph(f"${float(r['ingresos'] or 0):,.2f}",st["normal"])])
    t2 = Table(rows2,colWidths=[cw*0.06,cw*0.36,cw*0.2,cw*0.12,cw*0.26]); t2.setStyle(_tbl_style(st)); story.append(t2)
    # Grafico: top productos por ingresos
    prod_nombres = [str(r["producto__nombreProducto"] or "-")[:20] for r in top]
    prod_vals = [float(r["ingresos"] or 0) for r in top]
    if prod_nombres:
        story.append(Paragraph("Grafico: Top Productos por Ingresos", st["seccion"]))
        img = _grafico_barras(prod_nombres, prod_vals, "Top Productos por Ingresos ($)", "#8E44AD")
        story.append(_img_flowable(img, 15, 5))
    hr2, firma = _pdf_firma(st, usuario); story += [hr2, firma]
    # Dos pasadas para obtener total de paginas
    def _contar_paginas(story_items, doc_obj):
        from io import BytesIO as _BytesIO
        from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib.units import cm as _cm
        _W, _H = _A4
        _buf = _BytesIO()
        _frame = Frame(2*_cm, 1.5*_cm, _W-4*_cm, _H-3*_cm,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        _tpl = PageTemplate(id="cnt", frames=[_frame], onPage=lambda c,d: None)
        _doc2 = BaseDocTemplate(_buf, pagesize=_A4, pageTemplates=[_tpl])
        _doc2.build(story_items)
        _buf.seek(0)
        from pypdf import PdfReader as _PR
        return len(_PR(_buf).pages)

    import copy
    _total = _contar_paginas(copy.copy(story), doc)

    def _draw_page_nm(canvas_obj, doc_obj):
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib import colors as _c
        _W, _H = _A4
        canvas_obj.saveState()
        canvas_obj.setFillColor(_c.HexColor("#F4F6F8"))
        canvas_obj.rect(0, 0, _W, 1.2*st["cm"], fill=1, stroke=0)
        canvas_obj.setStrokeColor(_c.HexColor("#BDC3C7"))
        canvas_obj.line(0, 1.2*st["cm"], _W, 1.2*st["cm"])
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(_c.HexColor("#7F8C8D"))
        canvas_obj.drawString(2*st["cm"], 0.42*st["cm"],
            "Sistema de Gestion - Imprenta Tucan  |  " + st["hoy"].strftime("%d/%m/%Y"))
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.setFillColor(_c.HexColor("#1E3A5F"))
        canvas_obj.drawRightString(_W - 2*st["cm"], 0.42*st["cm"],
            "Pagina " + str(doc_obj.page) + " de " + str(_total))
        canvas_obj.restoreState()

    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
    from reportlab.lib.pagesizes import A4 as _A42
    from reportlab.lib.units import cm as _cm2
    _W2, _H2 = _A42
    _frame2 = Frame(2*_cm2, 1.5*_cm2, _W2-4*_cm2, _H2-3*_cm2,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="main")
    _tpl2 = PageTemplate(id="main", frames=[_frame2], onPage=_draw_page_nm)
    from io import BytesIO as _BytesIO2
    buffer = _BytesIO2()
    _doc_final = BaseDocTemplate(buffer, pagesize=_A42,
        pageTemplates=[_tpl2],
        title=st["titulo_inf"] + " - Imprenta Tucan")
    _doc_final.build(story)
    return _pdf_response(buffer, "informe_productos", request)


# ═══════════════════════════════════════════════════════════════════════════════
# INFORME 4: PROVEEDORES
# ═══════════════════════════════════════════════════════════════════════════════
@login_required
def informe_pdf_proveedores(request):
    from reportlab.platypus import Paragraph, Table
    from django.db.models import Count
    from django.utils.dateparse import parse_date
    desde = parse_date(request.GET.get("desde","") or "")
    hasta = parse_date(request.GET.get("hasta","") or "")
    usuario = str(request.user) if request.user.is_authenticated else "Sistema"
    buffer, doc, st, cw = _pdf_setup("Informe de Proveedores", request)
    story = []
    hdr, hr = _pdf_header(st, "Informe de Proveedores", _periodo_str(desde, hasta), usuario)
    story += [hdr, hr]
    story.append(Paragraph("Resumen de Proveedores", st["seccion"]))
    total = Proveedor.objects.count(); activos = Proveedor.objects.filter(activo=True).count()
    rows = [[Paragraph("<b>Indicador</b>",st["bold"]),Paragraph("<b>Valor</b>",st["bold"])],
            [Paragraph("Total proveedores",st["normal"]),Paragraph(f"<b>{total}</b>",st["bold"])],
            [Paragraph("Activos",st["normal"]),Paragraph(f"<b>{activos}</b>",st["bold"])],
            [Paragraph("Inactivos",st["normal"]),Paragraph(f"<b>{total-activos}</b>",st["bold"])]]
    t = Table(rows,colWidths=[cw*0.6,cw*0.4]); t.setStyle(_tbl_style(st)); story.append(t)
    story.append(Paragraph("Listado de Proveedores", st["seccion"]))
    provs = Proveedor.objects.annotate(n_insumos=Count("insumos")).order_by("nombre")
    rows2 = [[Paragraph("<b>Proveedor</b>",st["bold"]),Paragraph("<b>Contacto</b>",st["bold"]),Paragraph("<b>Insumos</b>",st["bold"]),Paragraph("<b>Estado</b>",st["bold"])]]
    for p in provs:
        rows2.append([Paragraph(str(p.nombre)[:35],st["normal"]),Paragraph(str(p.email or "-"),st["normal"]),Paragraph(str(p.n_insumos),st["normal"]),Paragraph("Activo" if p.activo else "Inactivo",st["normal"])])
    t2 = Table(rows2,colWidths=[cw*0.35,cw*0.35,cw*0.15,cw*0.15]); t2.setStyle(_tbl_style(st)); story.append(t2)
    # Grafico: insumos por proveedor (top 10)
    top_prov = Proveedor.objects.annotate(n=Count("insumos")).filter(n__gt=0).order_by("-n")[:10]
    prov_nombres = [str(p.nombre)[:15] for p in top_prov]
    prov_vals = [p.n for p in top_prov]
    if prov_nombres:
        story.append(Paragraph("Grafico: Insumos por Proveedor", st["seccion"]))
        img = _grafico_barras(prov_nombres, prov_vals, "Top 10 Proveedores por Cantidad de Insumos", "#E67E22")
        story.append(_img_flowable(img, 15, 5))
    hr2, firma = _pdf_firma(st, usuario); story += [hr2, firma]
    # Dos pasadas para obtener total de paginas
    def _contar_paginas(story_items, doc_obj):
        from io import BytesIO as _BytesIO
        from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib.units import cm as _cm
        _W, _H = _A4
        _buf = _BytesIO()
        _frame = Frame(2*_cm, 1.5*_cm, _W-4*_cm, _H-3*_cm,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        _tpl = PageTemplate(id="cnt", frames=[_frame], onPage=lambda c,d: None)
        _doc2 = BaseDocTemplate(_buf, pagesize=_A4, pageTemplates=[_tpl])
        _doc2.build(story_items)
        _buf.seek(0)
        from pypdf import PdfReader as _PR
        return len(_PR(_buf).pages)

    import copy
    _total = _contar_paginas(copy.copy(story), doc)

    def _draw_page_nm(canvas_obj, doc_obj):
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib import colors as _c
        _W, _H = _A4
        canvas_obj.saveState()
        canvas_obj.setFillColor(_c.HexColor("#F4F6F8"))
        canvas_obj.rect(0, 0, _W, 1.2*st["cm"], fill=1, stroke=0)
        canvas_obj.setStrokeColor(_c.HexColor("#BDC3C7"))
        canvas_obj.line(0, 1.2*st["cm"], _W, 1.2*st["cm"])
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(_c.HexColor("#7F8C8D"))
        canvas_obj.drawString(2*st["cm"], 0.42*st["cm"],
            "Sistema de Gestion - Imprenta Tucan  |  " + st["hoy"].strftime("%d/%m/%Y"))
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.setFillColor(_c.HexColor("#1E3A5F"))
        canvas_obj.drawRightString(_W - 2*st["cm"], 0.42*st["cm"],
            "Pagina " + str(doc_obj.page) + " de " + str(_total))
        canvas_obj.restoreState()

    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
    from reportlab.lib.pagesizes import A4 as _A42
    from reportlab.lib.units import cm as _cm2
    _W2, _H2 = _A42
    _frame2 = Frame(2*_cm2, 1.5*_cm2, _W2-4*_cm2, _H2-3*_cm2,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="main")
    _tpl2 = PageTemplate(id="main", frames=[_frame2], onPage=_draw_page_nm)
    from io import BytesIO as _BytesIO2
    buffer = _BytesIO2()
    _doc_final = BaseDocTemplate(buffer, pagesize=_A42,
        pageTemplates=[_tpl2],
        title=st["titulo_inf"] + " - Imprenta Tucan")
    _doc_final.build(story)
    return _pdf_response(buffer, "informe_proveedores", request)


# ═══════════════════════════════════════════════════════════════════════════════
# INFORME 5: INSUMOS / STOCK
# ═══════════════════════════════════════════════════════════════════════════════
@login_required
def informe_pdf_insumos(request):
    from reportlab.platypus import Paragraph, Table
    from django.db.models import Count, Sum
    buffer, doc, st, cw = _pdf_setup("Informe de Insumos y Stock", request)
    usuario = str(request.user) if request.user.is_authenticated else "Sistema"
    story = []
    hdr, hr = _pdf_header(st, "Informe de Insumos y Stock", _periodo_str(None, None), usuario)
    story += [hdr, hr]
    story.append(Paragraph("Resumen de Stock", st["seccion"]))
    total = Insumo.objects.count(); activos = Insumo.objects.filter(activo=True).count()
    sin_stock = Insumo.objects.filter(activo=True, stock__lte=0).count()
    bajo_min = Insumo.objects.filter(activo=True, stock__gt=0, stock__lte=10).count()
    rows = [[Paragraph("<b>Indicador</b>",st["bold"]),Paragraph("<b>Valor</b>",st["bold"])],
            [Paragraph("Total insumos",st["normal"]),Paragraph(f"<b>{total}</b>",st["bold"])],
            [Paragraph("Activos",st["normal"]),Paragraph(f"<b>{activos}</b>",st["bold"])],
            [Paragraph("Sin stock (=0)",st["normal"]),Paragraph(f"<b>{sin_stock}</b>",st["bold"])],
            [Paragraph("Stock bajo (<=10)",st["normal"]),Paragraph(f"<b>{bajo_min}</b>",st["bold"])]]
    t = Table(rows,colWidths=[cw*0.6,cw*0.4]); t.setStyle(_tbl_style(st)); story.append(t)
    story.append(Paragraph("Insumos con Stock Critico", st["seccion"]))
    criticos = Insumo.objects.filter(activo=True, stock__lte=10).order_by("stock")[:30]
    rows2 = [[Paragraph("<b>Codigo</b>",st["bold"]),Paragraph("<b>Nombre</b>",st["bold"]),Paragraph("<b>Stock</b>",st["bold"]),Paragraph("<b>Precio</b>",st["bold"])]]
    for ins in criticos:
        rows2.append([Paragraph(str(ins.codigo),st["normal"]),Paragraph(str(ins.nombre)[:35],st["normal"]),Paragraph(str(ins.stock),st["normal"]),Paragraph(f"${float(ins.precio_unitario):,.2f}",st["normal"])])
    if len(rows2)==1: rows2.append([Paragraph("Sin insumos criticos",st["normal"]),Paragraph("-",st["normal"]),Paragraph("-",st["normal"]),Paragraph("-",st["normal"])])
    t2 = Table(rows2,colWidths=[cw*0.2,cw*0.45,cw*0.1,cw*0.25]); t2.setStyle(_tbl_style(st)); story.append(t2)
    # Grafico: distribucion stock (torta)
    story.append(Paragraph("Grafico: Estado del Stock", st["seccion"]))
    stock_labels = ["Stock OK", "Stock Bajo (<=10)", "Sin Stock (=0)"]
    ok_count = Insumo.objects.filter(activo=True, stock__gt=10).count()
    stock_vals = [ok_count, bajo_min, sin_stock]
    stock_vals_filtrado = [(l, v) for l, v in zip(stock_labels, stock_vals) if v > 0]
    if stock_vals_filtrado:
        lbs, vls = zip(*stock_vals_filtrado)
        img = _grafico_torta(list(lbs), list(vls), "Estado del Stock de Insumos")
        story.append(_img_flowable(img, 9, 6))
    # Grafico: top 10 insumos con menos stock (barras)
    top_bajos = Insumo.objects.filter(activo=True, stock__gt=0).order_by("stock")[:10]
    if top_bajos:
        story.append(Paragraph("Grafico: Insumos con Menos Stock", st["seccion"]))
        ins_nombres = [str(i.codigo)[:12] for i in top_bajos]
        ins_vals = [i.stock for i in top_bajos]
        img2 = _grafico_barras(ins_nombres, ins_vals, "Insumos con Menos Stock", "#E74C3C")
        story.append(_img_flowable(img2, 15, 5))
    hr2, firma = _pdf_firma(st, usuario); story += [hr2, firma]
    # Dos pasadas para obtener total de paginas
    def _contar_paginas(story_items, doc_obj):
        from io import BytesIO as _BytesIO
        from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib.units import cm as _cm
        _W, _H = _A4
        _buf = _BytesIO()
        _frame = Frame(2*_cm, 1.5*_cm, _W-4*_cm, _H-3*_cm,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        _tpl = PageTemplate(id="cnt", frames=[_frame], onPage=lambda c,d: None)
        _doc2 = BaseDocTemplate(_buf, pagesize=_A4, pageTemplates=[_tpl])
        _doc2.build(story_items)
        _buf.seek(0)
        from pypdf import PdfReader as _PR
        return len(_PR(_buf).pages)

    import copy
    _total = _contar_paginas(copy.copy(story), doc)

    def _draw_page_nm(canvas_obj, doc_obj):
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib import colors as _c
        _W, _H = _A4
        canvas_obj.saveState()
        canvas_obj.setFillColor(_c.HexColor("#F4F6F8"))
        canvas_obj.rect(0, 0, _W, 1.2*st["cm"], fill=1, stroke=0)
        canvas_obj.setStrokeColor(_c.HexColor("#BDC3C7"))
        canvas_obj.line(0, 1.2*st["cm"], _W, 1.2*st["cm"])
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(_c.HexColor("#7F8C8D"))
        canvas_obj.drawString(2*st["cm"], 0.42*st["cm"],
            "Sistema de Gestion - Imprenta Tucan  |  " + st["hoy"].strftime("%d/%m/%Y"))
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.setFillColor(_c.HexColor("#1E3A5F"))
        canvas_obj.drawRightString(_W - 2*st["cm"], 0.42*st["cm"],
            "Pagina " + str(doc_obj.page) + " de " + str(_total))
        canvas_obj.restoreState()

    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
    from reportlab.lib.pagesizes import A4 as _A42
    from reportlab.lib.units import cm as _cm2
    _W2, _H2 = _A42
    _frame2 = Frame(2*_cm2, 1.5*_cm2, _W2-4*_cm2, _H2-3*_cm2,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="main")
    _tpl2 = PageTemplate(id="main", frames=[_frame2], onPage=_draw_page_nm)
    from io import BytesIO as _BytesIO2
    buffer = _BytesIO2()
    _doc_final = BaseDocTemplate(buffer, pagesize=_A42,
        pageTemplates=[_tpl2],
        title=st["titulo_inf"] + " - Imprenta Tucan")
    _doc_final.build(story)
    return _pdf_response(buffer, "informe_insumos", request)


# ═══════════════════════════════════════════════════════════════════════════════
# INFORME 6: COMPRAS
# ═══════════════════════════════════════════════════════════════════════════════
@login_required
def informe_pdf_compras(request):
    from reportlab.platypus import Paragraph, Table
    from django.db.models import Count, Sum
    from django.utils.dateparse import parse_date
    from compras.models import OrdenCompra, Remito, MovimientoStock, DetalleRemito
    desde = parse_date(request.GET.get("desde","") or "")
    hasta = parse_date(request.GET.get("hasta","") or "")
    usuario = str(request.user) if request.user.is_authenticated else "Sistema"
    buffer, doc, st, cw = _pdf_setup("Informe de Compras", request)
    story = []
    hdr, hr = _pdf_header(st, "Informe de Compras", _periodo_str(desde, hasta), usuario)
    story += [hdr, hr]
    qs_oc = OrdenCompra.objects.all()
    qs_rem = Remito.objects.all()
    if desde:
        qs_oc = qs_oc.filter(fecha_creacion__gte=desde)
        qs_rem = qs_rem.filter(fecha__gte=desde)
    if hasta:
        qs_oc = qs_oc.filter(fecha_creacion__lte=hasta)
        qs_rem = qs_rem.filter(fecha__lte=hasta)
    story.append(Paragraph("Resumen de Compras", st["seccion"]))
    rows = [[Paragraph("<b>Indicador</b>",st["bold"]),Paragraph("<b>Valor</b>",st["bold"])],
            [Paragraph("Ordenes de Compra",st["normal"]),Paragraph(f"<b>{qs_oc.count()}</b>",st["bold"])],
            [Paragraph("Remitos registrados",st["normal"]),Paragraph(f"<b>{qs_rem.count()}</b>",st["bold"])],
            [Paragraph("Movimientos de stock",st["normal"]),Paragraph(f"<b>{MovimientoStock.objects.count()}</b>",st["bold"])]]
    t = Table(rows,colWidths=[cw*0.6,cw*0.4]); t.setStyle(_tbl_style(st)); story.append(t)
    story.append(Paragraph("Ordenes de Compra", st["seccion"]))
    rows2 = [[Paragraph("<b>OC</b>",st["bold"]),Paragraph("<b>Proveedor</b>",st["bold"]),Paragraph("<b>Estado</b>",st["bold"]),Paragraph("<b>Fecha</b>",st["bold"]),Paragraph("<b>Total</b>",st["bold"])]]
    for oc in qs_oc.select_related("proveedor","estado").order_by("-fecha_creacion")[:20]:
        rows2.append([Paragraph(f"OC-{oc.pk:04d}",st["normal"]),Paragraph(str(oc.proveedor)[:30],st["normal"]),Paragraph(str(oc.estado),st["normal"]),Paragraph(oc.fecha_creacion.strftime("%d/%m/%y"),st["normal"]),Paragraph(f"${float(oc.monto_total):,.2f}",st["normal"])])
    if len(rows2)==1: rows2.append([Paragraph("Sin ordenes",st["normal"]),Paragraph("-",st["normal"]),Paragraph("-",st["normal"]),Paragraph("-",st["normal"]),Paragraph("-",st["normal"])])
    t2 = Table(rows2,colWidths=[cw*0.12,cw*0.33,cw*0.18,cw*0.15,cw*0.22]); t2.setStyle(_tbl_style(st)); story.append(t2)
    story.append(Paragraph("Remitos Registrados", st["seccion"]))
    rows3 = [[Paragraph("<b>Numero</b>",st["bold"]),Paragraph("<b>Proveedor</b>",st["bold"]),Paragraph("<b>Fecha</b>",st["bold"]),Paragraph("<b>Items</b>",st["bold"])]]
    for rem in qs_rem.select_related("proveedor").annotate(n_items=Count("detalles")).order_by("-fecha"):
        rows3.append([Paragraph(str(rem.numero),st["normal"]),Paragraph(str(rem.proveedor)[:30],st["normal"]),Paragraph(rem.fecha.strftime("%d/%m/%y"),st["normal"]),Paragraph(str(rem.n_items),st["normal"])])
    if len(rows3)==1: rows3.append([Paragraph("Sin remitos",st["normal"]),Paragraph("-",st["normal"]),Paragraph("-",st["normal"]),Paragraph("-",st["normal"])])
    t3 = Table(rows3,colWidths=[cw*0.2,cw*0.45,cw*0.2,cw*0.15]); t3.setStyle(_tbl_style(st)); story.append(t3)
    # Grafico: ordenes por estado (torta)
    oc_estados = qs_oc.values("estado__nombre").annotate(n=Count("id")).order_by("-n")
    oc_labels = [str(r["estado__nombre"] or "-") for r in oc_estados]
    oc_vals = [r["n"] for r in oc_estados]
    if oc_labels:
        story.append(Paragraph("Grafico: Ordenes de Compra por Estado", st["seccion"]))
        img = _grafico_torta(oc_labels, oc_vals, "Ordenes de Compra por Estado")
        story.append(_img_flowable(img, 9, 6))
    # Grafico: movimientos de stock por tipo
    from compras.models import MovimientoStock
    mov_tipos = MovimientoStock.objects.values("tipo").annotate(n=Count("id")).order_by("-n")
    mov_labels = [str(r["tipo"]) for r in mov_tipos]
    mov_vals = [r["n"] for r in mov_tipos]
    if mov_labels:
        story.append(Paragraph("Grafico: Movimientos de Stock por Tipo", st["seccion"]))
        img2 = _grafico_barras(mov_labels, mov_vals, "Movimientos de Stock por Tipo", "#1E3A5F")
        story.append(_img_flowable(img2, 12, 4))
    hr2, firma = _pdf_firma(st, usuario); story += [hr2, firma]
    # Dos pasadas para obtener total de paginas
    def _contar_paginas(story_items, doc_obj):
        from io import BytesIO as _BytesIO
        from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib.units import cm as _cm
        _W, _H = _A4
        _buf = _BytesIO()
        _frame = Frame(2*_cm, 1.5*_cm, _W-4*_cm, _H-3*_cm,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        _tpl = PageTemplate(id="cnt", frames=[_frame], onPage=lambda c,d: None)
        _doc2 = BaseDocTemplate(_buf, pagesize=_A4, pageTemplates=[_tpl])
        _doc2.build(story_items)
        _buf.seek(0)
        from pypdf import PdfReader as _PR
        return len(_PR(_buf).pages)

    import copy
    _total = _contar_paginas(copy.copy(story), doc)

    def _draw_page_nm(canvas_obj, doc_obj):
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib import colors as _c
        _W, _H = _A4
        canvas_obj.saveState()
        canvas_obj.setFillColor(_c.HexColor("#F4F6F8"))
        canvas_obj.rect(0, 0, _W, 1.2*st["cm"], fill=1, stroke=0)
        canvas_obj.setStrokeColor(_c.HexColor("#BDC3C7"))
        canvas_obj.line(0, 1.2*st["cm"], _W, 1.2*st["cm"])
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(_c.HexColor("#7F8C8D"))
        canvas_obj.drawString(2*st["cm"], 0.42*st["cm"],
            "Sistema de Gestion - Imprenta Tucan  |  " + st["hoy"].strftime("%d/%m/%Y"))
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.setFillColor(_c.HexColor("#1E3A5F"))
        canvas_obj.drawRightString(_W - 2*st["cm"], 0.42*st["cm"],
            "Pagina " + str(doc_obj.page) + " de " + str(_total))
        canvas_obj.restoreState()

    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame
    from reportlab.lib.pagesizes import A4 as _A42
    from reportlab.lib.units import cm as _cm2
    _W2, _H2 = _A42
    _frame2 = Frame(2*_cm2, 1.5*_cm2, _W2-4*_cm2, _H2-3*_cm2,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="main")
    _tpl2 = PageTemplate(id="main", frames=[_frame2], onPage=_draw_page_nm)
    from io import BytesIO as _BytesIO2
    buffer = _BytesIO2()
    _doc_final = BaseDocTemplate(buffer, pagesize=_A42,
        pageTemplates=[_tpl2],
        title=st["titulo_inf"] + " - Imprenta Tucan")
    _doc_final.build(story)
    return _pdf_response(buffer, "informe_compras", request)
