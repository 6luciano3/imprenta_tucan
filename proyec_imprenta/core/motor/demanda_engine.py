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
from .base import ProcesoInteligenteBase
from .config import MotorConfig


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
        except Exception:
            pass

        # 2) Media móvil de ConsumoRealInsumo
        meses = MotorConfig.get('DEMANDA_MESES_HISTORICO', cast=int) or 3
        cantidad = predecir_demanda_media_movil(insumo, periodo, meses=meses)
        if cantidad is not None and cantidad > 0:
            return int(cantidad)

        # 3) Media mensual de órdenes de compra últimos 6 meses
        try:
            from pedidos.models import OrdenCompra
            from django.utils import timezone
            from django.db.models import Sum
            hace_6m = timezone.now() - timedelta(days=180)
            agg = (OrdenCompra.objects
                   .filter(insumo=insumo, fecha_creacion__gte=hace_6m)
                   .aggregate(total=Sum('cantidad')))
            if agg['total']:
                return int(agg['total'] / 6.0)
        except Exception:
            pass

        # 4) Cantidad típica de compra del catálogo
        if insumo.cantidad:
            return int(insumo.cantidad)

        return 0

    # ------------------------------------------------------------------ #
    # Factor estacional                                                    #
    # ------------------------------------------------------------------ #

    def _factor_estacional(self, insumo, mes_actual: int) -> float:
        """
        Calcula el ratio de consumo del mismo mes historial vs. promedio general.

        Ejemplo: si marzo siempre consume el doble del promedio → factor=2.0.
        Rango acotado [0.5, 2.5] para evitar extremos con pocos datos.
        Requiere al menos 3 registros históricos para activarse.
        """
        try:
            from insumos.models import ConsumoRealInsumo
            from django.db.models import Avg

            consumos_todos = ConsumoRealInsumo.objects.filter(insumo=insumo)
            if consumos_todos.count() < 3:
                return 1.0

            avg_general = consumos_todos.aggregate(avg=Avg('cantidad_consumida'))['avg'] or 0
            if avg_general == 0:
                return 1.0

            mes_str = f'-{mes_actual:02d}'
            consumos_mes = consumos_todos.filter(periodo__endswith=mes_str)
            if not consumos_mes.exists():
                return 1.0

            avg_mes = consumos_mes.aggregate(avg=Avg('cantidad_consumida'))['avg'] or 0
            factor = avg_mes / avg_general
            return min(2.5, max(0.5, factor))
        except Exception:
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
        except Exception:
            pass

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
        factor_preventivo   = MotorConfig.get('DEMANDA_FACTOR_PREVENTIVO', cast=float) or 1.0
        stock_minimo_efectivo = max(stock_minimo, stock_minimo_global)

        demanda_ajustada = max(0, int(demanda_predicha * factor_estacional))

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
            except Exception:
                continue

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
        Registra el consumo real del insumo para mejorar las predicciones futuras.

        feedback esperado:
            {'insumo_id': int, 'periodo': 'YYYY-MM', 'cantidad_real': int}
        """
        insumo_id = feedback.get('insumo_id')
        periodo   = feedback.get('periodo')
        cantidad  = feedback.get('cantidad_real')
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
        except Exception:
            pass

