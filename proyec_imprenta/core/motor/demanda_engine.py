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

        Jerarquía:
            1. ProyeccionInsumo del período (dato oficial del motor de demanda).
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
    # Motor de reglas                                                      #
    # ------------------------------------------------------------------ #

    def evaluar_reglas(self, insumo, demanda_predicha: int) -> list:
        """
        Evalúa las reglas de negocio para el insumo y retorna acciones sugeridas.

        Umbrales configurables desde /configuracion/motor-demanda/:
            R1: stock <= DEMANDA_UMBRAL_CRITICO   → sin_stock_critico  (prioridad: alta)
            R2: stock < max(stock_minimo, STOCK_MINIMO_GLOBAL) → compra_urgente (prioridad: alta)
            R3: stock < demanda × DEMANDA_FACTOR_PREVENTIVO   → compra_preventiva (prioridad: media)
        """
        acciones = []
        stock_actual = int(insumo.stock or 0)
        stock_minimo = int(insumo.stock_minimo_sugerido or 0)

        # Leer umbrales configurados
        umbral_critico      = MotorConfig.get('DEMANDA_UMBRAL_CRITICO', cast=int) or 0
        stock_minimo_global = MotorConfig.get('STOCK_MINIMO_GLOBAL', cast=int) or 10
        factor_preventivo   = MotorConfig.get('DEMANDA_FACTOR_PREVENTIVO', cast=float) or 1.0

        # Mínimo efectivo: el mayor entre el calculado por historial y el global
        stock_minimo_efectivo = max(stock_minimo, stock_minimo_global)

        # R1 — sin stock crítico
        if stock_actual <= umbral_critico:
            # Sugerido: llevar al mínimo efectivo; solo usa demanda si supera al mínimo
            # y el insumo tiene historial real (evita valores ML sin datos).
            tiene_manual = insumo.stock_minimo_manual is not None
            sugerido_r1 = stock_minimo_efectivo if tiene_manual else max(demanda_predicha, stock_minimo_efectivo, 1)
            acciones.append({
                'tipo': 'sin_stock_critico',
                'insumo_id': insumo.idInsumo,
                'insumo_nombre': insumo.nombre,
                'stock_actual': stock_actual,
                'stock_minimo': stock_minimo_efectivo,
                'demanda_predicha': demanda_predicha,
                'cantidad_sugerida': max(sugerido_r1 - stock_actual, 1),
                'prioridad': 'alta',
            })
        # R2 — bajo mínimo
        elif stock_actual < stock_minimo_efectivo:
            acciones.append({
                'tipo': 'compra_urgente',
                'insumo_id': insumo.idInsumo,
                'insumo_nombre': insumo.nombre,
                'stock_actual': stock_actual,
                'stock_minimo': stock_minimo_efectivo,
                'demanda_predicha': demanda_predicha,
                'cantidad_sugerida': stock_minimo_efectivo - stock_actual,
                'prioridad': 'alta',
            })
        # R3 — bajo demanda proyectada × factor
        elif demanda_predicha > 0 and stock_actual < int(demanda_predicha * factor_preventivo):
            acciones.append({
                'tipo': 'compra_preventiva',
                'insumo_id': insumo.idInsumo,
                'insumo_nombre': insumo.nombre,
                'stock_actual': stock_actual,
                'stock_minimo': stock_minimo_efectivo,
                'demanda_predicha': demanda_predicha,
                'cantidad_sugerida': int(demanda_predicha * factor_preventivo) - stock_actual,
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

        for insumo in Insumo.objects.filter(activo=True, tipo=Insumo.TIPO_DIRECTO):
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
