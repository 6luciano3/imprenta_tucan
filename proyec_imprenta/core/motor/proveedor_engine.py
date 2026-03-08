"""
PI-2 — Motor Inteligente de Proveedores.

Evalúa cada proveedor con 4 criterios ponderados. Los pesos se leen desde
ProveedorParametro (BD) → sobreviven reinicios, evitando la pérdida de feedback.

Criterios:
    precio       — precio relativo vs. media global del mismo insumo/categoría.
    cumplimiento — ratio órdenes confirmadas / total.
    incidencias  — ratio órdenes rechazadas / total.
    disponibilidad — ratio consultas positivas / total (ConsultaStockProveedor).

Retroalimentación:
    El administrador puede ajustar los deltas de cada peso tras aceptar/rechazar
    una recomendación. Los nuevos pesos se normalizan y persisten en BD.
"""
from .base import ProcesoInteligenteBase
from .config import MotorConfig


class ProveedorInteligenteEngine(ProcesoInteligenteBase):
    nombre = "proveedores"

    # ------------------------------------------------------------------ #
    # Pesos                                                                #
    # ------------------------------------------------------------------ #

    def _get_pesos(self) -> dict:
        """Lee pesos desde BD (ProveedorParametro). Fallback a defaults."""
        return {
            'precio': MotorConfig.get('PESO_PRECIO', cast=float),
            'cumplimiento': MotorConfig.get('PESO_CUMPLIMIENTO', cast=float),
            'incidencias': MotorConfig.get('PESO_INCIDENCIAS', cast=float),
            'disponibilidad': MotorConfig.get('PESO_DISPONIBILIDAD', cast=float),
        }

    # ------------------------------------------------------------------ #
    # Métricas individuales                                                #
    # ------------------------------------------------------------------ #

    def _precio_relativo(self, proveedor, insumo=None) -> float:
        """
        Precio relativo normalizado min-max sobre todos los proveedores activos.
        0.0 = precio mínimo (más barato); 1.0 = precio máximo (más caro).

        Reemplaza la normalización por media*2 que saturaba para precios
        más del doble de la media sin discriminar entre ellos.

        - Con insumo: rango de precios del mismo insumo en todos los proveedores activos.
        - Sin insumo: rango de precios promedio por proveedor activo.
        - Rango nulo o sin datos: retorna 0.5 (neutro).
        """
        from django.db.models import Avg, Min, Max
        from insumos.models import Insumo as InsumoModel
        try:
            if insumo is not None:
                precio_insumo = float(insumo.precio_unitario or 0)
                stats = (
                    InsumoModel.objects
                    .filter(nombre=insumo.nombre, proveedor__activo=True)
                    .aggregate(min_p=Min('precio_unitario'), max_p=Max('precio_unitario'))
                )
                min_p = float(stats['min_p'] or 0)
                max_p = float(stats['max_p'] or 0)
            else:
                proveedor_avg = (
                    InsumoModel.objects
                    .filter(proveedor=proveedor)
                    .aggregate(avg=Avg('precio_unitario'))['avg']
                )
                if proveedor_avg is None:
                    return 0.5
                precio_insumo = float(proveedor_avg)
                # Min-max del precio promedio por proveedor activo
                rows = (
                    InsumoModel.objects
                    .filter(proveedor__activo=True)
                    .values('proveedor')
                    .annotate(avg_p=Avg('precio_unitario'))
                )
                avgs = [float(r['avg_p'] or 0) for r in rows if r['avg_p'] is not None]
                if not avgs:
                    return 0.5
                min_p, max_p = min(avgs), max(avgs)

            rango = max_p - min_p
            if rango < 0.0001:
                return 0.5  # todos los proveedores tienen el mismo precio
            return min(1.0, max(0.0, (precio_insumo - min_p) / rango))
        except Exception:
            return 0.5

    def _cumplimiento(self, proveedor, ordenes=None) -> float:
        """
        Proporción PONDERADA de órdenes confirmadas con decaimiento temporal exponencial.
        Órdenes recientes tienen mayor peso; órdenes antiguas impactan menos.
        Lambda (por día) configurable desde BD (CUMPLIMIENTO_DECAY_LAMBDA).
        Sin historial → 1.0 (beneficio de la duda).

        ordenes: lista pre-fetched (compartida con _incidencias para evitar 2 queries).
        """
        import math
        from django.utils import timezone
        if ordenes is None:
            from pedidos.models import OrdenCompra
            ordenes = list(
                OrdenCompra.objects.filter(proveedor=proveedor).order_by('-fecha_creacion')[:100]
            )
        if not ordenes:
            return 1.0
        lam = MotorConfig.get('CUMPLIMIENTO_DECAY_LAMBDA', cast=float) or 0.01
        ahora = timezone.now()
        peso_total = peso_confirmadas = 0.0
        for o in ordenes:
            dias = max(0, (ahora - o.fecha_creacion).days)
            w = math.exp(-lam * dias)
            peso_total += w
            if o.estado == 'confirmada':
                peso_confirmadas += w
        return peso_confirmadas / peso_total if peso_total > 0 else 1.0

    def _incidencias(self, proveedor, ordenes=None) -> float:
        """
        Proporción PONDERADA de órdenes rechazadas con decaimiento temporal exponencial.
        Órdenes recientes tienen mayor peso; órdenes antiguas impactan menos.
        Sin historial → 0.0 (sin incidencias conocidas).

        ordenes: lista pre-fetched (compartida con _cumplimiento para evitar 2 queries).
        """
        import math
        from django.utils import timezone
        if ordenes is None:
            from pedidos.models import OrdenCompra
            ordenes = list(
                OrdenCompra.objects.filter(proveedor=proveedor).order_by('-fecha_creacion')[:100]
            )
        if not ordenes:
            return 0.0
        lam = MotorConfig.get('CUMPLIMIENTO_DECAY_LAMBDA', cast=float) or 0.01
        ahora = timezone.now()
        peso_total = peso_rechazadas = 0.0
        for o in ordenes:
            dias = max(0, (ahora - o.fecha_creacion).days)
            w = math.exp(-lam * dias)
            peso_total += w
            if o.estado == 'rechazada':
                peso_rechazadas += w
        return peso_rechazadas / peso_total if peso_total > 0 else 0.0

    def _disponibilidad(self, proveedor, insumo=None) -> float:
        """
        Proporción de consultas de stock positivas en el período reciente.
        Filtra por los últimos DISPONIBILIDAD_DIAS días (default 90) y,
        si se indica, por insumo. Sin historial reciente → 1.0 (disponible).
        """
        from automatizacion.models import ConsultaStockProveedor
        from django.utils import timezone
        from datetime import timedelta
        dias = MotorConfig.get('DISPONIBILIDAD_DIAS', cast=int) or 90
        desde = timezone.now() - timedelta(days=dias)
        qs = ConsultaStockProveedor.objects.filter(proveedor=proveedor, creado__gte=desde)
        if insumo is not None:
            qs = qs.filter(insumo=insumo)
        if not qs.exists():
            return 1.0
        positivas = qs.filter(estado__in=['disponible', 'parcial']).count()
        return positivas / qs.count()

    def _latencia_promedio_dias(self, proveedor) -> float:
        """
        Latencia media de respuesta (fecha_creacion → fecha_respuesta) normalizada [0, 1].
        0.0 = responde instantáneamente (mejor score); 1.0 = supera LATENCIA_MAX_DIAS.
        Sin órdenes con fecha_respuesta registrada → 0.5 (neutro).
        """
        from pedidos.models import OrdenCompra
        max_dias = MotorConfig.get('LATENCIA_MAX_DIAS', cast=float) or 30.0
        qs = OrdenCompra.objects.filter(
            proveedor=proveedor,
            estado='confirmada',
            fecha_respuesta__isnull=False,
        )
        if not qs.exists():
            return 0.5  # neutro cuando no hay datos históricos de latencia
        total_dias = 0.0
        count = 0
        for o in qs:
            delta = (o.fecha_respuesta - o.fecha_creacion).days
            if delta >= 0:
                total_dias += delta
                count += 1
        if count == 0:
            return 0.5
        return min(1.0, max(0.0, (total_dias / count) / max_dias))

    # ------------------------------------------------------------------ #
    # Score ponderado (batch + individual)                                 #
    # ------------------------------------------------------------------ #

    def _calcular_scores_batch(self, proveedores, insumo=None) -> dict:
        """
        Calcula scores para una lista de proveedores en batch.
        Elimina el N+1 de recomendar(): en lugar de N*(4-5 queries) se
        ejecutan 4-5 queries totales para todos los proveedores.
        Retorna {proveedor_id: score}.
        """
        from pedidos.models import OrdenCompra
        from automatizacion.models import ConsultaStockProveedor
        from insumos.models import Insumo as InsumoModel
        from django.db.models import Avg, Min, Max, Count
        from django.utils import timezone
        from datetime import timedelta
        import math

        if not proveedores:
            return {}

        pesos = self._get_pesos()
        peso_latencia = MotorConfig.get('PESO_LATENCIA', cast=float) or 0.1
        lam = MotorConfig.get('CUMPLIMIENTO_DECAY_LAMBDA', cast=float) or 0.01
        dias_disp = MotorConfig.get('DISPONIBILIDAD_DIAS', cast=int) or 90
        max_dias_lat = MotorConfig.get('LATENCIA_MAX_DIAS', cast=float) or 30.0
        peso_sum = sum(pesos.values()) + peso_latencia

        prov_ids = [p.id for p in proveedores]
        ahora = timezone.now()
        desde_disp = ahora - timedelta(days=dias_disp)

        # ── 1) Precios relativos (1–2 queries) ───────────────────────────────────────
        try:
            if insumo is not None:
                precio_insumo = float(insumo.precio_unitario or 0)
                stats = (
                    InsumoModel.objects
                    .filter(nombre=insumo.nombre, proveedor__activo=True)
                    .aggregate(min_p=Min('precio_unitario'), max_p=Max('precio_unitario'))
                )
                min_p = float(stats['min_p'] or 0)
                max_p = float(stats['max_p'] or 0)
                rango = max_p - min_p
                precio_por_prov = {
                    p.id: (min(1.0, max(0.0, (precio_insumo - min_p) / rango)) if rango > 0.0001 else 0.5)
                    for p in proveedores
                }
            else:
                rows = (
                    InsumoModel.objects
                    .filter(proveedor__activo=True)
                    .values('proveedor_id')
                    .annotate(avg_p=Avg('precio_unitario'))
                )
                avg_map = {r['proveedor_id']: float(r['avg_p']) for r in rows if r['avg_p'] is not None}
                avgs = list(avg_map.values())
                rango = (max(avgs) - min(avgs)) if avgs else 0
                min_p = min(avgs) if avgs else 0
                precio_por_prov = {}
                for p in proveedores:
                    v = avg_map.get(p.id)
                    if v is None or rango < 0.0001:
                        precio_por_prov[p.id] = 0.5
                    else:
                        precio_por_prov[p.id] = min(1.0, max(0.0, (v - min_p) / rango))
        except Exception:
            precio_por_prov = {p.id: 0.5 for p in proveedores}

        # ── 2) Órdenes históricas: 1 query, agrupadas en Python ────────────────
        todas_ordenes = list(
            OrdenCompra.objects
            .filter(proveedor_id__in=prov_ids)
            .order_by('proveedor_id', '-fecha_creacion')
            .values('proveedor_id', 'estado', 'fecha_creacion', 'fecha_respuesta')
        )
        ordenes_por_prov: dict = {}
        conteo: dict = {}
        for o in todas_ordenes:
            pid = o['proveedor_id']
            if conteo.get(pid, 0) < 100:
                ordenes_por_prov.setdefault(pid, []).append(o)
                conteo[pid] = conteo.get(pid, 0) + 1

        # ── 3) Disponibilidad: 2 queries ────────────────────────────────────
        qs_disp = ConsultaStockProveedor.objects.filter(
            proveedor_id__in=prov_ids, creado__gte=desde_disp
        )
        if insumo is not None:
            qs_disp = qs_disp.filter(insumo=insumo)
        total_disp = dict(
            qs_disp.values('proveedor_id').annotate(n=Count('id')).values_list('proveedor_id', 'n')
        )
        pos_disp = dict(
            qs_disp.filter(estado__in=['disponible', 'parcial'])
            .values('proveedor_id').annotate(n=Count('id')).values_list('proveedor_id', 'n')
        )

        # ── 4) Calcular score por proveedor en Python ────────────────────────
        scores = {}
        for p in proveedores:
            try:
                pid = p.id
                ordenes = ordenes_por_prov.get(pid, [])
                if ordenes:
                    peso_total = peso_conf = peso_rech = 0.0
                    lat_dias = lat_count = 0
                    for o in ordenes:
                        dias = max(0, (ahora - o['fecha_creacion']).days)
                        w = math.exp(-lam * dias)
                        peso_total += w
                        if o['estado'] == 'confirmada':
                            peso_conf += w
                            if o['fecha_respuesta'] is not None:
                                delta = (o['fecha_respuesta'] - o['fecha_creacion']).days
                                if delta >= 0:
                                    lat_dias += delta
                                    lat_count += 1
                        elif o['estado'] == 'rechazada':
                            peso_rech += w
                    cumplimiento = peso_conf / peso_total if peso_total > 0 else 1.0
                    incidencias = peso_rech / peso_total if peso_total > 0 else 0.0
                    latencia = min(1.0, max(0.0, (lat_dias / lat_count) / max_dias_lat)) if lat_count > 0 else 0.5
                else:
                    cumplimiento, incidencias, latencia = 1.0, 0.0, 0.5

                total = total_disp.get(pid, 0)
                disponibilidad = (pos_disp.get(pid, 0) / total) if total > 0 else 1.0
                precio = precio_por_prov.get(pid, 0.5)

                score_bruto = (
                    pesos['precio']         * (1 - precio) +
                    pesos['cumplimiento']   * cumplimiento +
                    pesos['incidencias']    * (1 - incidencias) +
                    pesos['disponibilidad'] * disponibilidad +
                    peso_latencia           * (1 - latencia)
                )
                scores[pid] = round((score_bruto / peso_sum) * 100, 2) if peso_sum > 0 else 0.0
            except Exception:
                scores[p.id] = 0.0
        return scores

    def calcular_score(self, proveedor, insumo=None) -> float:
        """
        Score ponderado [0, 100]. Mayor es mejor.
        Incorpora 5 criterios: precio (min-max), cumplimiento (ponderado temporal),
        incidencias (ponderado temporal), disponibilidad (ventana reciente), latencia.
        Los pesos se normalizan por su suma para mantener la escala 0-100.
        """
        from pedidos.models import OrdenCompra
        pesos = self._get_pesos()
        peso_latencia = MotorConfig.get('PESO_LATENCIA', cast=float) or 0.1

        # Pre-fetch orders once to avoid duplicate queries in _cumplimiento and _incidencias
        ordenes = list(
            OrdenCompra.objects.filter(proveedor=proveedor).order_by('-fecha_creacion')[:100]
        )

        precio        = self._precio_relativo(proveedor, insumo)
        cumplimiento  = self._cumplimiento(proveedor, ordenes=ordenes)
        incidencias   = self._incidencias(proveedor, ordenes=ordenes)
        disponibilidad = self._disponibilidad(proveedor, insumo)
        latencia      = self._latencia_promedio_dias(proveedor)

        score_bruto = (
            pesos['precio']         * (1 - precio) +
            pesos['cumplimiento']   * cumplimiento +
            pesos['incidencias']    * (1 - incidencias) +
            pesos['disponibilidad'] * disponibilidad +
            peso_latencia           * (1 - latencia)
        )
        peso_sum = sum(pesos.values()) + peso_latencia
        return round((score_bruto / peso_sum) * 100, 2) if peso_sum > 0 else 0.0

    # ------------------------------------------------------------------ #
    # Recomendación                                                        #
    # ------------------------------------------------------------------ #

    def recomendar(self, insumo=None):
        """
        Calcula el score de todos los proveedores activos en batch, persiste en
        ScoreProveedor y retorna (mejor_proveedor, score).
        Usa _calcular_scores_batch() para evitar el N+1 de queries por proveedor.
        """
        from proveedores.models import Proveedor
        from automatizacion.models import ScoreProveedor
        from django.utils import timezone
        proveedores = list(Proveedor.objects.filter(activo=True))
        if not proveedores:
            return None, 0.0
        scores = self._calcular_scores_batch(proveedores, insumo)
        mejor = None
        mejor_score = -1.0
        for p in proveedores:
            score = scores.get(p.id, 0.0)
            ScoreProveedor.objects.update_or_create(
                proveedor=p,
                defaults={'score': score, 'actualizado': timezone.now()},
            )
            if score > mejor_score:
                mejor_score = score
                mejor = p
        return mejor, mejor_score

    def ejecutar(self, **kwargs) -> dict:
        """
        Recalcula scores de todos los proveedores activos y retorna el mejor.

        kwargs opcionales:
            insumo: instancia de Insumo para calcular el score en contexto.
        """
        insumo = kwargs.get('insumo')
        try:
            proveedor, score = self.recomendar(insumo)
            if proveedor:
                return {'estado': 'ok', 'proveedor': proveedor.nombre, 'score': score}
            return {'estado': 'sin_resultado'}
        except Exception as e:
            return {'estado': 'error', 'detalle': str(e)}

    # ------------------------------------------------------------------ #
    # Retroalimentación persistente                                        #
    # ------------------------------------------------------------------ #

    def retroalimentar(self, feedback: dict) -> None:
        """
        Ajusta los pesos de los criterios y los persiste en ProveedorParametro.

        feedback esperado:
            {'precio': float, 'cumplimiento': float,
             'incidencias': float, 'disponibilidad': float}

        Cada valor es un delta (positivo o negativo). Los pesos resultantes
        se renormalizan para que sumen 1.
        """
        pesos = self._get_pesos()
        for k, delta in feedback.items():
            if k in pesos:
                pesos[k] = max(0.0, min(1.0, pesos[k] + float(delta)))
        total = sum(pesos.values()) or 1.0
        for k in pesos:
            pesos[k] = round(pesos[k] / total, 4)
            MotorConfig.set_proveedor(f'PESO_{k.upper()}', pesos[k])
