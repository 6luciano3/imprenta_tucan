"""
Motor de Reglas centralizado para todos los procesos inteligentes.

Este módulo es la única fuente de verdad para las reglas de negocio.
Tanto DemandaInteligenteEngine como las tareas Celery deben delegar aquí.
"""


def evaluar_reglas(contexto: dict, umbrales: dict | None = None) -> list:
    """
    Evalúa reglas de negocio sobre el contexto y retorna una lista de decisiones.

    Reglas implementadas:
        R1: stock <= umbral_critico (default 0)          → sin_stock_critico  (prioridad: critica)
        R2: stock  <  max(stock_minimo, smg)              → compra_urgente     (prioridad: alta)
        R3: stock  <  demanda_predicha * factor           → compra_preventiva  (prioridad: media)
        R4: pedidos_retrasados > umbral_retraso           → alerta_retraso     (prioridad: alta)

    Args:
        contexto: dict con claves:
            'insumos': list of dicts con id, nombre, stock, stock_minimo, demanda_predicha
            'pedidos_retrasados': int (opcional)
            'umbral_retraso': int (opcional, default 3)
        umbrales: dict opcional con parámetros configurables:
            'umbral_critico'     : int   (default 0)    — R1: stock ≤ este valor es crítico
            'stock_minimo_global': int   (default 0)    — R2: piso mínimo global
            'factor_preventivo'  : float (default 1.0)  — R3: multiplicador de demanda
            'umbral_retraso'     : int   (default 3)    — R4: umbral pedidos retrasados

    Returns:
        Lista de dicts de decisiones, cada una con:
            tipo, insumo_id, nombre, prioridad, accion, cantidad_sugerida,
            stock_actual, stock_minimo_efectivo, demanda_predicha, regla_aplicada,
            explicacion (razón legíble de la decisión)
    """
    um = umbrales or {}
    umbral_critico      = int(um.get('umbral_critico', 0))
    stock_minimo_global = int(um.get('stock_minimo_global', 0))
    factor_preventivo   = float(um.get('factor_preventivo', 1.0))

    decisiones = []

    for insumo in contexto.get('insumos', []):
        stock         = int(insumo.get('stock', 0))
        stock_minimo  = int(insumo.get('stock_minimo', 0))
        demanda       = int(insumo.get('demanda_predicha', 0))
        insumo_id     = insumo.get('id')
        nombre        = insumo.get('nombre', str(insumo_id))

        # Mínimo efectivo: mayor entre el calculado por historial y el global
        stock_minimo_efectivo = max(stock_minimo, stock_minimo_global)
        umbral_r3             = int(demanda * factor_preventivo)

        # R1 — Stock crítico (llega o supera el umbral crítico)
        if stock <= umbral_critico:
            cantidad_sug = max(stock_minimo_efectivo - stock, demanda, 1)
            decisiones.append({
                'tipo': 'sin_stock_critico',
                'insumo_id': insumo_id,
                'nombre': nombre,
                'prioridad': 'critica',
                'accion': 'compra_inmediata',
                'cantidad_sugerida': cantidad_sug,
                'stock_actual': stock,
                'stock_minimo_efectivo': stock_minimo_efectivo,
                'demanda_predicha': demanda,
                'regla_aplicada': 'R1',
                'explicacion': (
                    f'Stock ({stock}) ≤ umbral crítico ({umbral_critico}). '
                    f'Compra inmediata de {cantidad_sug} unidades para cubrir mínimo.'
                ),
            })

        # R2 — Stock bajo mínimo (pero sin ser crítico)
        elif stock < stock_minimo_efectivo:
            cantidad_sug = stock_minimo_efectivo - stock
            decisiones.append({
                'tipo': 'compra_urgente',
                'insumo_id': insumo_id,
                'nombre': nombre,
                'prioridad': 'alta',
                'accion': 'compra_urgente',
                'cantidad_sugerida': cantidad_sug,
                'stock_actual': stock,
                'stock_minimo_efectivo': stock_minimo_efectivo,
                'demanda_predicha': demanda,
                'regla_aplicada': 'R2',
                'explicacion': (
                    f'Stock ({stock}) < mínimo efectivo ({stock_minimo_efectivo}). '
                    f'Reponer {cantidad_sug} unidades para llegar al mínimo.'
                ),
            })

        # R3 — Stock bajo demanda proyectada (compra preventiva)
        elif demanda > 0 and stock < umbral_r3:
            cantidad_sug = umbral_r3 - stock
            decisiones.append({
                'tipo': 'compra_preventiva',
                'insumo_id': insumo_id,
                'nombre': nombre,
                'prioridad': 'media',
                'accion': 'compra_preventiva',
                'cantidad_sugerida': cantidad_sug,
                'stock_actual': stock,
                'stock_minimo_efectivo': stock_minimo_efectivo,
                'demanda_predicha': demanda,
                'regla_aplicada': 'R3',
                'explicacion': (
                    f'Stock ({stock}) < demanda proyectada ({demanda}) × factor ({factor_preventivo}) = {umbral_r3}. '
                    f'Compra preventiva de {cantidad_sug} unidades.'
                ),
            })

    # R4 — Pedidos retrasados
    umbral_ret = int(um.get('umbral_retraso', contexto.get('umbral_retraso', 3)))
    retrasados = int(contexto.get('pedidos_retrasados', 0))
    if retrasados > umbral_ret:
        decisiones.append({
            'tipo': 'alerta_retraso',
            'cantidad_pedidos': retrasados,
            'prioridad': 'alta',
            'accion': 'revisar_produccion',
            'regla_aplicada': 'R4',
            'explicacion': (
                f'{retrasados} pedidos retrasados superan el umbral de {umbral_ret}. '
                f'Revisar capacidad de producción.'
            ),
        })

    return decisiones
