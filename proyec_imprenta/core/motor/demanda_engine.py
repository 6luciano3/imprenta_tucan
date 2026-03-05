"""
PI-3 — Motor Inteligente de Demanda e Insumos.

Pipeline:
    1. Para cada insumo activo, predice la demanda del período usando media
       móvil sobre ConsumoRealInsumo (N meses configurables desde BD).
    2. Aplica el motor de reglas: compara stock actual vs. stock_minimo_sugerido
       y vs. demanda predicha.
    3. Retorna lista de acciones sugeridas (compras urgentes, preventivas, alertas).

Retroalimentación:
    Registra consumo real en ConsumoRealInsumo para mejorar futuras predicciones.
"""
from .base import ProcesoInteligenteBase
from .config import MotorConfig


class DemandaInteligenteEngine(ProcesoInteligenteBase):
    nombre = "demanda"

    # ------------------------------------------------------------------ #
    # Predicción                                                           #
    # ------------------------------------------------------------------ #

    def predecir_demanda(self, insumo, periodo: str) -> int:
        """
        Predice la demanda del insumo para el período dado.

        Algoritmo: media móvil simple de los últimos N meses de ConsumoRealInsumo.
        Fallback: stock_minimo_sugerido del insumo (basado en consumo promedio mensual).

        Retorna 0 si no hay datos ni mínimo sugerido.
        """
        from insumos.models import predecir_demanda_media_movil
        meses = MotorConfig.get('DEMANDA_MESES_HISTORICO', cast=int) or 3
        cantidad = predecir_demanda_media_movil(insumo, periodo, meses=meses)
        if cantidad is not None:
            return int(cantidad)
        return int(insumo.stock_minimo_sugerido or 0)

    # ------------------------------------------------------------------ #
    # Motor de reglas                                                      #
    # ------------------------------------------------------------------ #

    def evaluar_reglas(self, insumo, demanda_predicha: int) -> list:
        """
        Evalúa las reglas de negocio para el insumo y retorna acciones sugeridas.

        Reglas (en orden de prioridad):
            R1: stock == 0                    → sin_stock_critico  (prioridad: alta)
            R2: stock < stock_minimo_sugerido → compra_urgente     (prioridad: alta)
            R3: stock < demanda_predicha      → compra_preventiva  (prioridad: media)
        """
        acciones = []
        stock_actual = int(insumo.stock or 0)
        stock_minimo = int(insumo.stock_minimo_sugerido or 0)

        if stock_actual == 0:
            acciones.append({
                'tipo': 'sin_stock_critico',
                'insumo_id': insumo.idInsumo,
                'insumo_nombre': insumo.nombre,
                'stock_actual': stock_actual,
                'stock_minimo': stock_minimo,
                'demanda_predicha': demanda_predicha,
                'cantidad_sugerida': max(demanda_predicha, stock_minimo, 1),
                'prioridad': 'alta',
            })
        elif stock_actual < stock_minimo:
            acciones.append({
                'tipo': 'compra_urgente',
                'insumo_id': insumo.idInsumo,
                'insumo_nombre': insumo.nombre,
                'stock_actual': stock_actual,
                'stock_minimo': stock_minimo,
                'demanda_predicha': demanda_predicha,
                'cantidad_sugerida': stock_minimo - stock_actual,
                'prioridad': 'alta',
            })
        elif demanda_predicha > 0 and stock_actual < demanda_predicha:
            acciones.append({
                'tipo': 'compra_preventiva',
                'insumo_id': insumo.idInsumo,
                'insumo_nombre': insumo.nombre,
                'stock_actual': stock_actual,
                'stock_minimo': stock_minimo,
                'demanda_predicha': demanda_predicha,
                'cantidad_sugerida': demanda_predicha - stock_actual,
                'prioridad': 'media',
            })

        return acciones

    # ------------------------------------------------------------------ #
    # Ejecución principal                                                  #
    # ------------------------------------------------------------------ #

    def ejecutar(self, **kwargs) -> dict:
        """
        Itera todos los insumos activos, predice demanda y aplica reglas.

        Retorna:
            {
                'estado': 'ok',
                'periodo': '2026-03',
                'insumos_procesados': int,
                'acciones_sugeridas': int,
                'urgentes': int,          # prioridad 'alta'
                'detalle': [...],         # lista de acciones
            }
        """
        from insumos.models import Insumo
        from django.utils import timezone

        periodo = timezone.now().strftime('%Y-%m')
        acciones_totales = []
        insumos_procesados = 0

        for insumo in Insumo.objects.filter(activo=True):
            try:
                demanda = self.predecir_demanda(insumo, periodo)
                acciones = self.evaluar_reglas(insumo, demanda)
                acciones_totales.extend(acciones)
                insumos_procesados += 1
            except Exception:
                continue

        urgentes = [a for a in acciones_totales if a['prioridad'] == 'alta']
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
        periodo = feedback.get('periodo')
        cantidad = feedback.get('cantidad_real')
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
