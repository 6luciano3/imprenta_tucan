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
