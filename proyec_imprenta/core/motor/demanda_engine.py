"""
PI-3 — Motor Inteligente de Demanda e Insumos.

Pipeline:
    1. Para cada insumo activo, predice la demanda del período usando media
       móvil sobre ConsumoRealInsumo (N meses configurables desde BD).
    2. Aplica factor estacional (ratio consumo mismo mes vs. promedio general).
    3. Delega la evaluación de reglas al motor centralizado (core/ai_rules/rules_engine.py).
    4. Retorna lista de acciones con explicación e intervalo de confianza.

Retroalimentación:
    Registra consumo real en ConsumoRealInsumo para mejorar futuras predicciones.
"""
import logging
from .base import ProcesoInteligenteBase
from .config import MotorConfig

logger = logging.getLogger(__name__)


class DemandaInteligenteEngine(ProcesoInteligenteBase):
    nombre = "demanda"

    # ------------------------------------------------------------------ #
    # Predicción base                                                      #
    # ------------------------------------------------------------------ #

    def predecir_demanda(self, insumo, periodo: str) -> int:
        """
        Predice la demanda del insumo para el período dado.

        Jerarquía:
            1. ProyeccionInsumo del período (dato oficial).
            2. Media móvil de ConsumoRealInsumo de los últimos N meses.
            3. Media mensual de OrdenCompra de los últimos 6 meses (proxy real).
            4. insumo.cantidad (cantidad típica de compra del catálogo).

        Retorna 0 si no hay datos en ninguna fuente.
        """
        from insumos.models import predecir_demanda_media_movil, ProyeccionInsumo
        from datetime import timedelta

        # 1) ProyeccionInsumo oficial
        try:
            proy = ProyeccionInsumo.objects.filter(
                insumo=insumo, periodo=periodo
            ).first()
            if proy and proy.cantidad_proyectada:
                return int(proy.cantidad_proyectada)
        except Exception as e:
            logger.warning("predecir_demanda [insumo=%s] fuente 1 error: %s", getattr(insumo, 'idInsumo', '?'), e)

        # 2) Media móvil ponderada de ConsumoRealInsumo
        meses = MotorConfig.get('DEMANDA_MESES_HISTORICO', cast=int) or 3
        cantidad = predecir_demanda_media_movil(insumo, periodo, meses=meses)
        if cantidad is not None and cantidad > 0:
            return int(cantidad)

        # 3) Media mensual de órdenes de compra últimos 6 meses
        # Divide por el número real de meses con compras, no siempre por 6.
        try:
            from pedidos.models import OrdenCompra
            from django.utils import timezone
            from django.db.models import Sum
            from django.db.models.functions import TruncMonth
            hace_6m = timezone.now() - timedelta(days=180)
            qs_compras = OrdenCompra.objects.filter(insumo=insumo, fecha_creacion__gte=hace_6m)
            agg = qs_compras.aggregate(total=Sum('cantidad'))
            meses_activos = (
                qs_compras
                .annotate(mes=TruncMonth('fecha_creacion'))
                .values('mes')
                .distinct()
                .count()
            )
            if agg['total'] and meses_activos > 0:
                return int(agg['total'] / meses_activos)
        except Exception as e:
            logger.warning("predecir_demanda [insumo=%s] fuente 3 error: %s", getattr(insumo, 'idInsumo', '?'), e)

        # 4) Cantidad típica de compra del catálogo
        if insumo.cantidad:
            return int(insumo.cantidad)

        return 0

    # ------------------------------------------------------------------ #
    # Factor estacional                                                    #
    # ------------------------------------------------------------------ #

    def _factor_estacional(self, insumo, mes_actual: int) -> float:
        """
        Calcula el factor estacional ponderando los años recientes con mayor peso.

        Separa los datos por año para capturar tanto estacionalidad como tendencia:
        - Años recientes aportan más al promedio general y al promedio del mes.
        - Factor acotado a [0.5, 2.5]; requiere al menos 3 registros para activarse.
        """
        try:
            from insumos.models import ConsumoRealInsumo
            from collections import defaultdict

            consumos_vals = list(
                ConsumoRealInsumo.objects
                .filter(insumo=insumo)
                .values_list('periodo', 'cantidad_consumida')
            )
            if len(consumos_vals) < 3:
                return 1.0

            # Calcular pesos por año: año más reciente obtiene mayor peso
            años = sorted({int(str(p)[:4]) for p, c in consumos_vals if c is not None})
            if not años:
                return 1.0
            peso_por_año = {a: i + 1 for i, a in enumerate(años)}  # año más antiguo=1, más reciente=N

            # Promedio general ponderado por año
            suma_pond_gral = 0.0
            suma_pesos_gral = 0.0
            mes_str = f'-{mes_actual:02d}'
            suma_pond_mes = 0.0
            suma_pesos_mes = 0.0

            for periodo_str, c in consumos_vals:
                if c is None:
                    continue
                año_val = int(str(periodo_str)[:4])
                peso = peso_por_año.get(año_val, 1)
                val = float(c)
                suma_pond_gral  += val * peso
                suma_pesos_gral += peso
                if str(periodo_str).endswith(mes_str):
                    suma_pond_mes  += val * peso
                    suma_pesos_mes += peso

            if suma_pesos_gral == 0 or suma_pond_gral == 0:
                return 1.0
            if suma_pesos_mes == 0:
                return 1.0

            avg_general = suma_pond_gral / suma_pesos_gral
            avg_mes     = suma_pond_mes  / suma_pesos_mes
            factor = avg_mes / avg_general
            return min(2.5, max(0.5, factor))
        except Exception as e:
            logger.warning("_factor_estacional [insumo=%s] error: %s", getattr(insumo, 'idInsumo', '?'), e)
            return 1.0

    # ------------------------------------------------------------------ #
    # Intervalo de confianza                                               #
    # ------------------------------------------------------------------ #

    def predecir_con_intervalo(self, insumo, periodo: str) -> dict:
        """
        Predice la demanda y calcula un intervalo de confianza basado en la
        desviación estándar del historial de consumo.

        Returns:
            {
                'prediccion': int,
                'intervalo_bajo': int,
                'intervalo_alto': int,
                'confianza': 'alta' | 'media' | 'baja',
                'n_muestras': int,
                'factor_estacional': float,
            }
        """
        import statistics

        try:
            mes_actual = int(periodo.split('-')[1])
        except Exception:
            mes_actual = 1

        prediccion_base = self.predecir_demanda(insumo, periodo)
        factor = self._factor_estacional(insumo, mes_actual)
        prediccion = max(0, int(prediccion_base * factor))

        # Calcular desviación estándar con historial
        try:
            from insumos.models import ConsumoRealInsumo
            año, mes = map(int, periodo.split('-'))
            periodos = []
            for i in range(1, 7):
                m = mes - i
                y = año
                if m <= 0:
                    m += 12
                    y -= 1
                periodos.append(f'{y:04d}-{m:02d}')

            consumos = list(ConsumoRealInsumo.objects
                            .filter(insumo=insumo, periodo__in=periodos)
                            .values_list('cantidad_consumida', flat=True))

            n = len(consumos)
            if n >= 2:
                std = statistics.stdev(consumos)
                confianza = 'alta' if n >= 4 else 'media'
                return {
                    'prediccion': prediccion,
                    'intervalo_bajo': max(0, int(prediccion - std)),
                    'intervalo_alto': int(prediccion + std),
                    'confianza': confianza,
                    'n_muestras': n,
                    'factor_estacional': round(factor, 3),
                }
        except Exception as e:
            logger.warning("predecir_con_intervalo [insumo=%s] error calculando std: %s", getattr(insumo, 'idInsumo', '?'), e)

        # Sin suficiente historial: intervalo ±20 %
        return {
            'prediccion': prediccion,
            'intervalo_bajo': int(prediccion * 0.8),
            'intervalo_alto': int(prediccion * 1.2),
            'confianza': 'baja',
            'n_muestras': 0,
            'factor_estacional': round(factor, 3),
        }

    # ------------------------------------------------------------------ #
    # Motor de reglas (delega al motor centralizado)                       #
    # ------------------------------------------------------------------ #

    def evaluar_reglas(self, insumo, demanda_predicha: int, factor_estacional: float = 1.0) -> list:
        """
        Delega la evaluación al motor centralizado core/ai_rules/rules_engine.py.

        Construye el contexto con los umbrales configurables desde BD y enrichece
        la salida con campos adicionales para compatibilidad con el dashboard.
        """
        from core.ai_rules.rules_engine import evaluar_reglas as _evaluar_reglas

        stock_actual  = int(insumo.stock or 0)
        stock_minimo  = int(insumo.stock_minimo_sugerido or 0)

        umbral_critico      = MotorConfig.get('DEMANDA_UMBRAL_CRITICO', cast=int) or 0
        stock_minimo_global = MotorConfig.get('STOCK_MINIMO_GLOBAL', cast=int) or 10
        # Default 1.5: activar alerta preventiva al 150 % de la demanda proyectada,
        # dando margen de reacción real antes de llegar al límite de stock.
        factor_preventivo   = MotorConfig.get('DEMANDA_FACTOR_PREVENTIVO', cast=float) or 1.5
        stock_minimo_efectivo = max(stock_minimo, stock_minimo_global)

        demanda_ajustada = max(0, int(demanda_predicha * factor_estacional))

        # ── Sanity caps para PYME — valores leídos desde Configuración ─────────
        _cap_max    = int(MotorConfig.get('DEMANDA_CAP_MENSUAL_MAX',      cast=int)   or 100)
        _cap_piso   = int(MotorConfig.get('DEMANDA_CAP_MENSUAL_PISO',     cast=int)   or 5)
        _cap_factor = float(MotorConfig.get('DEMANDA_CAP_FACTOR_DEMANDA', cast=float) or 2.0)
        _cap_smin   = float(MotorConfig.get('DEMANDA_CAP_FACTOR_STOCK_MIN', cast=float) or 1.5)

        # Cap 1 — demanda mensual: usa cantidad_compra_sugerida si está cargado,
        # de lo contrario usa stock_actual acotado entre [piso, max].
        _ref_mensual = int(insumo.cantidad_compra_sugerida or 0)
        if _ref_mensual == 0:
            _ref_mensual = max(min(stock_actual, _cap_max), _cap_piso)
        demanda_ajustada = min(demanda_ajustada, int(_ref_mensual * _cap_factor))

        # Cap 2 — stock_minimo_efectivo: evita que valores de semilla inflados
        # (ej. stock_minimo_manual=1500) generen sugerencias de R2 absurdas.
        _stock_min_cap = max(int(demanda_ajustada * _cap_smin), stock_minimo_global, 5)
        stock_minimo_efectivo = min(stock_minimo_efectivo, _stock_min_cap)

        contexto = {
            'insumos': [{
                'id': insumo.idInsumo,
                'nombre': insumo.nombre,
                'stock': stock_actual,
                'stock_minimo': stock_minimo_efectivo,
                'demanda_predicha': demanda_ajustada,
            }]
        }
        umbrales = {
            'umbral_critico': umbral_critico,
            'stock_minimo_global': stock_minimo_global,
            'factor_preventivo': factor_preventivo,
        }

        raw = _evaluar_reglas(contexto, umbrales)

        # Enriquecer con campos adicionales para compatibilidad con el dashboard
        resultado = []
        for accion in raw:
            resultado.append({
                **accion,
                'insumo_id': insumo.idInsumo,
                'insumo_nombre': insumo.nombre,
                'stock_actual': stock_actual,
                'stock_minimo': stock_minimo_efectivo,
                'demanda_predicha': demanda_predicha,
                'demanda_ajustada_estacional': demanda_ajustada,
                'factor_estacional': round(factor_estacional, 3),
            })
        return resultado

    # ------------------------------------------------------------------ #
    # Ejecución principal                                                  #
    # ------------------------------------------------------------------ #

    def ejecutar(self, **kwargs) -> dict:
        """
        Itera todos los insumos activos directos, predice demanda con factor
        estacional y aplica reglas delegando al motor centralizado.

        Retorna:
            {
                'estado': 'ok',
                'periodo': '2026-03',
                'insumos_procesados': int,
                'acciones_sugeridas': int,
                'urgentes': int,
                'detalle': [...],
            }
        """
        from insumos.models import Insumo
        from django.utils import timezone

        periodo = timezone.now().strftime('%Y-%m')
        try:
            mes_actual = int(periodo.split('-')[1])
        except Exception:
            mes_actual = 1

        acciones_totales = []
        insumos_procesados = 0

        for insumo in Insumo.objects.filter(activo=True, tipo=Insumo.TIPO_DIRECTO):
            try:
                demanda         = self.predecir_demanda(insumo, periodo)
                factor          = self._factor_estacional(insumo, mes_actual)
                acciones        = self.evaluar_reglas(insumo, demanda, factor_estacional=factor)
                acciones_totales.extend(acciones)
                insumos_procesados += 1
            except Exception as e:
                logger.warning("ejecutar: error procesando insumo %s: %s", getattr(insumo, 'idInsumo', '?'), e)
                continue

        # R4 — Pedidos retrasados (evaluación global, fuera del bucle por insumo)
        try:
            from pedidos.models import Pedido
            from core.ai_rules.rules_engine import evaluar_reglas as _evaluar_reglas
            umbral_ret = int(MotorConfig.get('DEMANDA_UMBRAL_RETRASO', cast=int) or 3)
            pedidos_retrasados = Pedido.objects.filter(
                estado__nombre__icontains='retras'
            ).count()
            contexto_r4 = {
                'insumos': [],
                'pedidos_retrasados': pedidos_retrasados,
                'umbral_retraso': umbral_ret,
            }
            acciones_totales.extend(_evaluar_reglas(contexto_r4))
        except Exception as e:
            logger.warning("ejecutar: R4 pedidos retrasados error: %s", e)

        urgentes = [a for a in acciones_totales if a.get('prioridad') in ('alta', 'critica')]
        return {
            'estado': 'ok',
            'periodo': periodo,
            'insumos_procesados': insumos_procesados,
            'acciones_sugeridas': len(acciones_totales),
            'urgentes': len(urgentes),
            'detalle': acciones_totales,
        }

    # ------------------------------------------------------------------ #
    # Retroalimentación                                                    #
    # ------------------------------------------------------------------ #

    def retroalimentar(self, feedback: dict) -> None:
        """
        Registra el consumo real y loguea la precisión de la predicción anterior.

        feedback esperado:
            {
                'insumo_id': int,
                'periodo': 'YYYY-MM',
                'cantidad_real': int,
                'cantidad_predicha': int  (opcional — para medir precisión)
            }
        """
        insumo_id        = feedback.get('insumo_id')
        periodo          = feedback.get('periodo')
        cantidad         = feedback.get('cantidad_real')
        cantidad_pred    = feedback.get('cantidad_predicha')
        if not all([insumo_id, periodo, cantidad]):
            return
        try:
            from insumos.models import ConsumoRealInsumo, Insumo
            insumo = Insumo.objects.get(idInsumo=insumo_id)
            ConsumoRealInsumo.objects.update_or_create(
                insumo=insumo,
                periodo=periodo,
                defaults={'cantidad_consumida': int(cantidad)},
            )
            # Auto-comparación: si se proveyó la predicción anterior, registrar precisión
            if cantidad_pred is not None:
                real     = int(cantidad)
                pred     = int(cantidad_pred)
                error_abs = abs(real - pred)
                error_pct = round(error_abs / real * 100, 1) if real > 0 else None
                logger.info(
                    "Retroalimentación [insumo=%s %s] periodo=%s "
                    "predicho=%d real=%d error_abs=%d error_pct=%s%%",
                    insumo_id, getattr(insumo, 'nombre', ''),
                    periodo, pred, real, error_abs,
                    error_pct if error_pct is not None else 'N/A',
                )
            else:
                logger.info(
                    "Retroalimentación [insumo=%s %s] periodo=%s real=%d registrado",
                    insumo_id, getattr(insumo, 'nombre', ''), periodo, int(cantidad),
                )
        except Exception as e:
            logger.warning("retroalimentar [insumo=%s] error: %s", insumo_id, e)


