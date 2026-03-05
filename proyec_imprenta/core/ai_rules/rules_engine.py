# Motor de Reglas para automatizaciones


def evaluar_reglas(contexto: dict) -> list:
    """
    Evalúa reglas de negocio sobre el contexto y retorna una lista de decisiones.

    Reglas implementadas:
        R1: stock == 0                        → alerta_sin_stock    (prioridad: critica)
        R2: stock < stock_minimo_sugerido     → sugerir_compra      (prioridad: alta)
        R3: stock < demanda_predicha          → sugerir_compra      (prioridad: media)
        R4: pedidos_retrasados > umbral       → alerta_retraso      (prioridad: alta)

    contexto esperado:
        {
            'insumos': [
                {
                    'id': int,
                    'nombre': str,
                    'stock': int,
                    'stock_minimo': int,
                    'demanda_predicha': int,
                }
            ],
            'pedidos_retrasados': int,   # opcional
            'umbral_retraso': int,       # opcional, default 3
        }
    """
    decisiones = []

    for insumo in contexto.get('insumos', []):
        stock = int(insumo.get('stock', 0))
        stock_minimo = int(insumo.get('stock_minimo', 0))
        demanda = int(insumo.get('demanda_predicha', 0))
        insumo_id = insumo.get('id')
        nombre = insumo.get('nombre', str(insumo_id))

        if stock == 0:
            decisiones.append({
                'tipo': 'alerta_sin_stock',
                'insumo_id': insumo_id,
                'nombre': nombre,
                'prioridad': 'critica',
                'accion': 'compra_inmediata',
                'cantidad_sugerida': max(demanda, stock_minimo, 1),
            })
        elif stock < stock_minimo:
            decisiones.append({
                'tipo': 'sugerir_compra',
                'insumo_id': insumo_id,
                'nombre': nombre,
                'prioridad': 'alta',
                'accion': 'compra_urgente',
                'cantidad_sugerida': stock_minimo - stock,
            })
        elif demanda > 0 and stock < demanda:
            decisiones.append({
                'tipo': 'sugerir_compra',
                'insumo_id': insumo_id,
                'nombre': nombre,
                'prioridad': 'media',
                'accion': 'compra_preventiva',
                'cantidad_sugerida': demanda - stock,
            })

    umbral_retraso = int(contexto.get('umbral_retraso', 3))
    retrasados = int(contexto.get('pedidos_retrasados', 0))
    if retrasados > umbral_retraso:
        decisiones.append({
            'tipo': 'alerta_retraso',
            'cantidad_pedidos': retrasados,
            'prioridad': 'alta',
            'accion': 'revisar_produccion',
        })

    return decisiones
