import re, pathlib
txt = pathlib.Path('automatizacion/tasks.py').read_text(encoding='utf-8')
nueva = '''
@shared_task
def tarea_generar_ofertas():
    try:
        from automatizacion.views_combos import generar_combo_para_cliente
        now = timezone.now()
        periodo_conf = Parametro.get('RANKING_PERIODICIDAD', 'mensual')
        periodo_str = now.strftime('%Y-%m') if periodo_conf != 'trimestral' else f"{now.year}-Q{(now.month-1)//3+1}"
        default_rules = [
            {'nombre':'Alto desempeno','condiciones':{'score_gte':80},'accion':{'tipo':'descuento','titulo_prefijo':'Combo Premium','descripcion':'Descuento exclusivo por ser cliente de alto valor.','parametros':{'descuento':15}}},
            {'nombre':'Fidelizacion','condiciones':{'decline_periods_gte':2,'decline_delta_lte':-10},'accion':{'tipo':'fidelizacion','titulo_prefijo':'Combo Fidelizacion','descripcion':'Condiciones especiales para retomar compras.','parametros':{'dias_sin_interes':30}}},
            {'nombre':'Criticidad','condiciones':{'crit_norm_gte':0.7},'accion':{'tipo':'prioridad_stock','titulo_prefijo':'Combo Stock Prioritario','descripcion':'Reserva garantizada en insumos criticos.','parametros':{'prioridad':'alta'}}},
            {'nombre':'Buen margen','condiciones':{'margen_norm_gte':0.6},'accion':{'tipo':'promocion','titulo_prefijo':'Combo Especial','descripcion':'Bonificacion en servicios complementarios.','parametros':{'bonificacion':'servicio_complementario'}}},
            {'nombre':'Estandar','condiciones':{},'accion':{'tipo':'promocion','titulo_prefijo':'Combo Personalizado','descripcion':'Oferta segun tu historial de compras.','parametros':{}}},
        ]
        reglas = Parametro.get('OFERTAS_REGLAS_JSON', default_rules)
        generadas = 0
        historicos_cliente = {}
        for rc in RankingCliente.objects.select_related('cliente').all():
            cliente = rc.cliente
            rh = RankingHistorico.objects.filter(cliente=cliente, periodo=periodo_str).first()
            metricas = rh.metricas if rh else {}
            crit_norm = float(metricas.get('crit_norm', 0) or 0)
            margen_norm = float(metricas.get('margen_norm', 0) or 0)
            if cliente.id not in historicos_cliente:
                historicos_cliente[cliente.id] = list(RankingHistorico.objects.filter(cliente=cliente).order_by('-generado')[:5])
            historicos = historicos_cliente[cliente.id]
            decline_periods, decline_delta = 0, 0.0
            for i in range(1, len(historicos)):
                delta = float(historicos[i-1].score) - float(historicos[i].score)
                if delta < 0: decline_periods += 1
                decline_delta = min(decline_delta, delta)
            try:
                combo = generar_combo_para_cliente(cliente)
            except Exception:
                combo = None
            for regla in reglas:
                cond = regla.get('condiciones', {})
                ok = True
                if 'score_gte' in cond: ok = ok and float(rc.score) >= float(cond['score_gte'])
                if 'crit_norm_gte' in cond: ok = ok and crit_norm >= float(cond['crit_norm_gte'])
                if 'margen_norm_gte' in cond: ok = ok and margen_norm >= float(cond['margen_norm_gte'])
                if 'decline_periods_gte' in cond: ok = ok and decline_periods >= int(cond['decline_periods_gte'])
                if 'decline_delta_lte' in cond: ok = ok and decline_delta <= float(cond['decline_delta_lte'])
                if not ok: continue
                accion = regla.get('accion', {})
                tipo = accion.get('tipo', 'promocion')
                titulo_prefijo = accion.get('titulo_prefijo', 'Oferta personalizada')
                titulo = f"{titulo_prefijo} - {combo.nombre}" if combo else titulo_prefijo
                if OfertaPropuesta.objects.filter(cliente=cliente, tipo=tipo, periodo=periodo_str).exists(): continue
                OfertaPropuesta.objects.create(
                    cliente=cliente, titulo=titulo, descripcion=accion.get('descripcion',''),
                    tipo=tipo, estado='pendiente', periodo=periodo_str,
                    score_al_generar=rc.score, parametros=accion.get('parametros',{}),
                )
                generadas += 1
                break
        return f"generar_ofertas: {generadas} propuestas generadas ({periodo_str})"
    except Exception as e:
        return f"generar_ofertas: error {e}"
'''
patron = r'\n@shared_task\ndef tarea_generar_ofertas\(\):.*?(?=\n@shared_task|\Z)'
nuevo_txt = re.sub(patron, nueva, txt, flags=re.DOTALL)
if nuevo_txt != txt:
    pathlib.Path('automatizacion/tasks.py').write_text(nuevo_txt, encoding='utf-8')
    print('tasks.py parcheado OK')
else:
    print('ADVERTENCIA: patron no encontrado, verificar manualmente')
