from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count

from automatizacion.models import RankingCliente, ScoreProveedor, RankingHistorico, OfertaPropuesta
import requests
from clientes.models import Cliente
from configuracion.models import Parametro, RecetaProducto
from productos.models import ProductoInsumo
from pedidos.models import Pedido
from proveedores.models import Proveedor

# Integraciones AI/Rules (placeholders con llamadas reales si se completan módulos)
try:
    from core.ai_ml.demand_prediction import predecir_demanda
except Exception:
    predecir_demanda = None

try:
    from core.ai_rules.rules_engine import evaluar_reglas
except Exception:
    evaluar_reglas = None


@shared_task
def tarea_prediccion_demanda():
    # Ejecutar predicción de demanda para insumos críticos si está disponible
    if predecir_demanda is None:
        return "prediccion_demanda: módulo no disponible"
    # Ejemplo mínimo (debería iterar insumos y su histórico real)
    try:
        # Placeholder: no hay modelo de Insumo en este módulo
        return "prediccion_demanda: ejecutado (placeholder)"
    except Exception as e:
        return f"prediccion_demanda: error {e}"


@shared_task
def tarea_anticipacion_compras():
    # Aplicar reglas de anticipación si hay motor de reglas
    if evaluar_reglas is None:
        return "anticipacion_compras: rules engine no disponible"
    try:
        contexto = {"fecha": timezone.now()}
        decisiones = evaluar_reglas(contexto)
        return f"anticipacion_compras: {len(decisiones)} decisiones"
    except Exception as e:
        return f"anticipacion_compras: error {e}"


@shared_task
def tarea_ranking_clientes():
    # DEMO: Asignar puntajes inventados para mostrar los 4 tipos de clientes
    # Premium >= 90, Estratégico >= 60, Estándar >= 30, Nuevo < 30
    from clientes.models import Cliente
    clientes = list(Cliente.objects.all())
    if len(clientes) >= 4:
        scores_demo = [95, 75, 45, 15]
        for i, score in enumerate(scores_demo):
            c = clientes[i]
            RankingCliente.objects.update_or_create(
                cliente_id=c.id,
                defaults={'score': score}
            )
            Cliente.objects.filter(id=c.id).update(
                puntaje_estrategico=score,
                fecha_ultima_actualizacion=timezone.now()
            )
        return "Puntajes demo asignados a los primeros 4 clientes."
    # Recalcular RankingCliente basado en algoritmo multicriterio configurable (últimos N días)
    try:
        # Parámetros
        periodo_conf = Parametro.get('RANKING_PERIODICIDAD', 'mensual')  # 'mensual' | 'trimestral'
        ventana_dias = Parametro.get('RANKING_VENTANA_DIAS', 90)  # por defecto 90
        umbral_precio_critico = Parametro.get('INSUMO_CRITICO_UMBRAL_PRECIO', 500.0)

        desde = timezone.now().date() - timedelta(days=int(ventana_dias))
        # Agregados básicos: total y cantidad de pedidos
        pedidos_qs = Pedido.objects.filter(fecha_pedido__gte=desde)
        agregados = (
            pedidos_qs
            .values('cliente_id')
            .annotate(total=Sum('monto_total'), cantidad=Count('id'))
        )
        if not agregados:
            return "ranking_clientes: sin datos recientes"

        # Productos que usan insumos críticos (por precio)
        productos_criticos = set(
            RecetaProducto.objects.filter(insumos__precio_unitario__gte=umbral_precio_critico)
            .values_list('producto_id', flat=True)
            .distinct()
        )

        # Precalcular costo unitario por producto (para margen)
        producto_ids = list(pedidos_qs.values_list('producto_id', flat=True).distinct())
        costo_unitario_por_producto = {}
        if producto_ids:
            # Traer receta BOM por producto y sumar cantidad_por_unidad * precio_unitario
            bom = ProductoInsumo.objects.select_related('insumo').filter(producto_id__in=producto_ids)
            for pi in bom:
                pid = pi.producto_id
                costo_unit = costo_unitario_por_producto.get(pid, 0.0)
                costo_unit += float(pi.cantidad_por_unidad) * float(pi.insumo.precio_unitario or 0)
                costo_unitario_por_producto[pid] = costo_unit

        # Métricas por cliente
        # Frecuencia: pedidos por mes dentro de la ventana
        meses_ventana = max(1, int(int(ventana_dias) / 30))
        # Construir mapa cliente -> métricas
        cliente_metrics = {}
        # Para margen, iterar pedidos del cliente
        pedidos_por_cliente = {}
        for p in pedidos_qs.select_related('producto').all():
            pedidos_por_cliente.setdefault(p.cliente_id, []).append(p)

        for a in agregados:
            cliente_id = a['cliente_id']
            total = float(a['total'] or 0)
            cant = int(a['cantidad'] or 0)
            freq = cant / meses_ventana
            # Consumo crítico: total de pedidos con productos críticos
            crit_total = (
                Pedido.objects.filter(fecha_pedido__gte=desde, cliente_id=cliente_id, producto_id__in=productos_criticos)
                .aggregate(s=Sum('monto_total'))['s'] or 0
            )
            # Margen total: ingresos - costo insumos (usando BOM por unidad)
            margin_total = 0.0
            for p in pedidos_por_cliente.get(cliente_id, []):
                costo_unit = float(costo_unitario_por_producto.get(p.producto_id, 0.0))
                costo_total = costo_unit * float(p.cantidad or 0)
                ingreso = float(p.monto_total or 0)
                margin_total += max(0.0, ingreso - costo_total)
            cliente_metrics[cliente_id] = {
                'total': total,
                'cant': cant,
                'freq': float(freq),
                'crit_total': float(crit_total),
                'margin_total': float(margin_total),
            }

        # Normalización
        max_total = max(m['total'] for m in cliente_metrics.values()) or 1
        max_cant = max(m['cant'] for m in cliente_metrics.values()) or 1
        max_freq = max(m['freq'] for m in cliente_metrics.values()) or 1
        max_crit = max(m['crit_total'] for m in cliente_metrics.values()) or 1
        max_margin = max(m['margin_total'] for m in cliente_metrics.values()) or 1

        # Pesos configurables (porcentaje)
        peso_cant = float(Parametro.get('RANKING_PESO_CANTIDAD', 25)) / 100.0
        peso_valor = float(Parametro.get('RANKING_PESO_VALOR_TOTAL', 30)) / 100.0
        peso_freq = float(Parametro.get('RANKING_PESO_FRECUENCIA', 20)) / 100.0
        peso_crit = float(Parametro.get('RANKING_PESO_CONSUMO_CRITICO', 20)) / 100.0
        peso_margen = float(Parametro.get('RANKING_PESO_MARGEN', 30)) / 100.0

        # Determinar periodo string
        now = timezone.now()
        if periodo_conf == 'trimestral':
            q = (now.month - 1) // 3 + 1
            periodo_str = f"{now.year}-Q{q}"
        else:
            periodo_str = now.strftime('%Y-%m')

        # Calcular score y actualizar registros
        # Intentar importar el modelo ML de valor futuro
        try:
            from core.ai_ml.valor_cliente import predecir_valor_cliente
        except Exception:
            predecir_valor_cliente = None

        for cliente_id, m in cliente_metrics.items():
            total_norm = (m['total']) / max_total
            cant_norm = (m['cant']) / max_cant
            freq_norm = (m['freq']) / max_freq
            crit_norm = (m['crit_total']) / max_crit
            margen_norm = (m['margin_total']) / max_margin
            # Normalizar por suma de pesos para mantener escala 0-100
            peso_sum = max(0.0001, (peso_cant + peso_valor + peso_freq + peso_crit + peso_margen))
            score_reglas = round(
                ((peso_cant * cant_norm) +
                 (peso_valor * total_norm) +
                 (peso_freq * freq_norm) +
                 (peso_crit * crit_norm) +
                 (peso_margen * margen_norm)) / peso_sum, 4
            ) * 100.0

            # Si hay modelo ML, usarlo como parte del score (ejemplo: promedio 50% reglas, 50% ML)
            if predecir_valor_cliente:
                features = {
                    'total_compras': m['total'],
                    'frecuencia': m['freq'],
                    'margen': margen_norm,
                    'ofertas_aceptadas': 0,  # Puedes agregar más features reales
                }
                try:
                    score_ml = predecir_valor_cliente(features)
                    score = 0.5 * score_reglas + 0.5 * score_ml
                except Exception:
                    score = score_reglas
            else:
                score = score_reglas


            # Piso mínimo: si el cliente tiene al menos un pedido, el score mínimo es 10
            if m['cant'] > 0 and score < 10:
                score = 10.0

            RankingCliente.objects.update_or_create(
                cliente_id=cliente_id,
                defaults={'score': score}
            )

            # Actualizar cliente
            Cliente.objects.filter(id=cliente_id).update(
                puntaje_estrategico=score,
                fecha_ultima_actualizacion=timezone.now()
            )

            # Histórico y variación
            previo = RankingHistorico.objects.filter(cliente_id=cliente_id).order_by('-generado').first()
            variacion = 0.0
            if previo and previo.periodo != periodo_str:
                variacion = round(score - float(previo.score), 4)

            RankingHistorico.objects.update_or_create(
                cliente_id=cliente_id, periodo=periodo_str,
                defaults={
                    'score': score,
                    'variacion': variacion,
                    'metricas': {
                        'total_norm': round(total_norm, 4),
                        'cant_norm': round(cant_norm, 4),
                        'freq_norm': round(freq_norm, 4),
                        'crit_norm': round(crit_norm, 4),
                        'margen_norm': round(margen_norm, 4),
                    }
                }
            )

        return f"ranking_clientes: {len(cliente_metrics)} clientes actualizados ({periodo_str})"
    except Exception as e:
        return f"ranking_clientes: error {e}"


@shared_task
def tarea_recalcular_scores_proveedores():
    # Recalcular ScoreProveedor para todos los proveedores activos
    try:
        from automatizacion.api.services import ProveedorInteligenteService
        count = 0
        for proveedor in Proveedor.objects.filter(activo=True):
            score = ProveedorInteligenteService.calcular_score(proveedor, insumo=None)
            ScoreProveedor.objects.update_or_create(
                proveedor=proveedor,
                defaults={'score': score}
            )
            count += 1
        return f"scores_proveedores: {count} proveedores actualizados"
    except Exception as e:
        return f"scores_proveedores: error {e}"


@shared_task
def tarea_generar_ofertas():
    """
    Genera UNA OfertaPropuesta por cliente segun su categoria de score:
      Premium    (score >= 90): 15% descuento
      Estrategico(60 <= score < 90): 10% descuento
      Estandar   (30 <= score < 60):  7% descuento
      Nuevo      (score < 30):         5% descuento
    """
    try:
        from automatizacion.views_combos import generar_combo_para_cliente

        now = timezone.now()
        periodo_conf = Parametro.get('RANKING_PERIODICIDAD', 'mensual')
        periodo_str = now.strftime('%Y-%m') if periodo_conf != 'trimestral' else f"{now.year}-Q{(now.month-1)//3+1}"

        CATEGORIAS = [
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

        generadas = 0

        for rc in RankingCliente.objects.select_related('cliente').all():
            cliente = rc.cliente
            score = float(rc.score or 0)

            # Determinar categoria
            categoria = None
            for cat in CATEGORIAS:
                min_ok = cat['score_min'] is None or score >= cat['score_min']
                max_ok = cat['score_max'] is None or score < cat['score_max']
                if min_ok and max_ok:
                    categoria = cat
                    break

            if not categoria:
                continue

            # Evitar duplicado para este cliente/periodo/tipo
            ya_existe = OfertaPropuesta.objects.filter(
                cliente=cliente,
                tipo=categoria['tipo'],
                periodo=periodo_str,
            ).exists()
            if ya_existe:
                continue

            # Generar combo personalizado
            try:
                combo = generar_combo_para_cliente(cliente)
            except Exception:
                combo = None

            titulo = f"{categoria['titulo_prefijo']} - {combo.nombre}" if combo else categoria['titulo_prefijo']

            OfertaPropuesta.objects.create(
                cliente=cliente,
                titulo=titulo,
                descripcion=categoria['descripcion'],
                tipo=categoria['tipo'],
                estado='pendiente',
                periodo=periodo_str,
                score_al_generar=rc.score,
                parametros={'descuento': categoria['descuento'], 'categoria': categoria['nombre']},
            )
            generadas += 1

        return f"generar_ofertas: {generadas} propuestas generadas ({periodo_str})"
    except Exception as e:
        return f"generar_ofertas: error {e}"

@shared_task
def tarea_alertas_retraso():
    # Emitir alertas según reglas/umbrales (placeholder)
    try:
        return "alertas_retraso: ejecutado (placeholder)"
    except Exception as e:
        return f"alertas_retraso: error {e}"


@shared_task
def tarea_automatizacion_presupuestos_ponderada():
    """Detecta necesidades de compra y genera propuestas automáticas:
    - Cruza pedidos recientes y stock de insumos
    - Recomienda proveedor óptimo (precio, cumplimiento, incidencias, disponibilidad)
    - Genera borrador de Orden de Compra
    - Registra consulta de stock al proveedor
    """
    try:
        from decimal import Decimal
        from django.db import transaction
        from pedidos.services import calcular_consumo_pedido, verificar_stock_consumo
        from automatizacion.api.services import ProveedorInteligenteService, CRITERIOS_PESOS
        from automatizacion.models import CompraPropuesta, ConsultaStockProveedor
        from pedidos.models import OrdenCompra
        from insumos.models import Insumo

        # 1) Revisar pedidos recientes (últimos 7 días) y/o parametrizable
        ventana_dias = int(Parametro.get('AUTOPRESUPUESTO_VENTANA_DIAS', 7))
        desde = timezone.now().date() - timedelta(days=ventana_dias)
        pedidos_recientes = Pedido.objects.filter(fecha_pedido__gte=desde).select_related('producto')

        propuestas_creadas = 0

        for pedido in pedidos_recientes:
            consumo = calcular_consumo_pedido(pedido)
            ok, faltantes = verificar_stock_consumo(consumo)
            if ok:
                continue  # no hay faltante
            for insumo_id, faltan in faltantes.items():
                try:
                    insumo = Insumo.objects.get(idInsumo=insumo_id)
                except Insumo.DoesNotExist:
                    continue
                cantidad_req = int(Decimal(str(faltan)))
                # 2) Recomendar proveedor óptimo
                proveedor = ProveedorInteligenteService.recomendar_proveedor(insumo)
                # 3) Generar borrador de Orden de Compra
                with transaction.atomic():
                    oc = OrdenCompra.objects.create(
                        insumo=insumo,
                        cantidad=cantidad_req,
                        proveedor=proveedor,
                        estado='sugerida',
                        comentario=f"Auto por pedido {pedido.id}: faltante {cantidad_req}"
                    )
                    # 4) Registrar consulta de stock
                    consulta = ConsultaStockProveedor.objects.create(
                        proveedor=proveedor,
                        insumo=insumo,
                        cantidad=cantidad_req,
                        estado='pendiente',
                        respuesta={}
                    )
                    # --- INTEGRACIÓN REAL: consulta HTTP si el proveedor tiene api_stock_url ---
                    if proveedor.api_stock_url:
                        try:
                            resp = requests.post(
                                proveedor.api_stock_url,
                                json={
                                    'insumo_id': insumo.id,
                                    'cantidad': cantidad_req
                                },
                                timeout=10
                            )
                            data = resp.json()
                            estado = data.get('estado')  # 'disponible', 'parcial', 'no', etc.
                            detalle = data.get('detalle', '')
                            if estado in {'disponible', 'parcial', 'no'}:
                                consulta.estado = estado
                                consulta.respuesta = {'detalle': detalle}
                                consulta.save()
                        except Exception as e:
                            consulta.estado = 'error'
                            consulta.respuesta = {'detalle': str(e)}
                            consulta.save()
                    # 5) Crear propuesta consolidada
                    CompraPropuesta.objects.create(
                        insumo=insumo,
                        cantidad_requerida=cantidad_req,
                        proveedor_recomendado=proveedor,
                        pesos_usados=CRITERIOS_PESOS,
                        motivo_trigger='pedido_mayor_stock',
                        estado='consultado',
                        borrador_oc=oc,
                        consulta_stock=consulta,
                    )
                    propuestas_creadas += 1
                    # 6) Notificar al proveedor por email
                    try:
                        from automatizacion.services import enviar_email_orden_compra_proveedor
                        enviar_email_orden_compra_proveedor(oc)
                    except Exception:
                        pass

        # 6) Revisar insumos bajo stock mínimo global
        stock_minimo = int(Parametro.get('STOCK_MINIMO_GLOBAL', 10))
        bajos = Insumo.objects.filter(stock__lte=stock_minimo, activo=True)
        for insumo in bajos:
            # evitar duplicar si ya hay propuesta reciente del mismo insumo
            ya = CompraPropuesta.objects.filter(insumo=insumo, creada__gte=timezone.now()-timedelta(days=3)).exists()
            if ya:
                continue
            proveedor = ProveedorInteligenteService.recomendar_proveedor(insumo)
            cantidad_req = max(1, stock_minimo * 2)
            with transaction.atomic():
                oc = OrdenCompra.objects.create(
                    insumo=insumo,
                    cantidad=cantidad_req,
                    proveedor=proveedor,
                    estado='sugerida',
                    comentario=f"Auto stock mínimo: sugerido {cantidad_req}"
                )
                consulta = ConsultaStockProveedor.objects.create(
                    proveedor=proveedor,
                    insumo=insumo,
                    cantidad=cantidad_req,
                    estado='pendiente',
                    respuesta={}
                )
                # --- INTEGRACIÓN REAL: consulta HTTP si el proveedor tiene api_stock_url ---
                if proveedor.api_stock_url:
                    try:
                        resp = requests.post(
                            proveedor.api_stock_url,
                            json={
                                'insumo_id': insumo.id,
                                'cantidad': cantidad_req
                            },
                            timeout=10
                        )
                        data = resp.json()
                        estado = data.get('estado')
                        detalle = data.get('detalle', '')
                        if estado in {'disponible', 'parcial', 'no'}:
                            consulta.estado = estado
                            consulta.respuesta = {'detalle': detalle}
                            consulta.save()
                    except Exception as e:
                        consulta.estado = 'error'
                        consulta.respuesta = {'detalle': str(e)}
                        consulta.save()
                CompraPropuesta.objects.create(
                    insumo=insumo,
                    cantidad_requerida=cantidad_req,
                    proveedor_recomendado=proveedor,
                    pesos_usados=CRITERIOS_PESOS,
                    motivo_trigger='stock_minimo_vencido',
                    estado='consultado',
                    borrador_oc=oc,
                    consulta_stock=consulta,
                )
                propuestas_creadas += 1
                # Notificar al proveedor por email
                try:
                    from automatizacion.services import enviar_email_orden_compra_proveedor
                    enviar_email_orden_compra_proveedor(oc)
                except Exception:
                    pass

        # 7) Auto-aceptación según parámetros si hay respuesta disponible y el proveedor cumple umbral
        auto_aprobar = bool(Parametro.get('AUTO_APROBAR_PROPUESTAS', False))
        aceptadas_auto = 0
        if auto_aprobar:
            umbral_score = float(Parametro.get('UMBRAL_SCORE_PROVEEDOR', 70))
            # Propuestas en estado consultado o con respuesta disponible
            from automatizacion.models import CompraPropuesta
            from automatizacion.models import ScoreProveedor
            propuestas = CompraPropuesta.objects.select_related('insumo', 'proveedor_recomendado', 'consulta_stock', 'borrador_oc')\
                .filter(estado__in=['consultado', 'respuesta_disponible'])
            for p in propuestas:
                try:
                    consulta_ok = p.consulta_stock and p.consulta_stock.estado == 'disponible'
                    proveedor = p.proveedor_recomendado
                    score_ok = False
                    if proveedor:
                        sp = ScoreProveedor.objects.filter(proveedor=proveedor).first()
                        score_ok = (sp and float(sp.score or 0) >= umbral_score)
                    if consulta_ok and score_ok:
                        oc = p.borrador_oc
                        if oc:
                            oc.estado = 'confirmada'
                            oc.save()
                        insumo = p.insumo
                        if proveedor:
                            insumo.proveedor = proveedor
                        insumo.stock = (insumo.stock or 0) + int(p.cantidad_requerida or 0)
                        insumo.save(update_fields=['proveedor', 'stock'])
                        p.estado = 'aceptada'
                        p.decision = 'aceptar'
                        p.comentario_admin = 'Aceptada automáticamente por umbrales'
                        p.save()
                        aceptadas_auto += 1
                except Exception:
                    # seguir con las demás
                    pass

        return f"auto_presupuesto: {propuestas_creadas} propuestas generadas; {aceptadas_auto} aceptadas automáticamente"
    except Exception as e:
        return f"auto_presupuesto: error {e}"
