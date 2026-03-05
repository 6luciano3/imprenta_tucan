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
        Precio relativo del proveedor en escala [0, 1].
        0 = más barato que la media; 1 = el doble de la media o más.

        - Con insumo: compara precio_unitario del insumo vs. media del mismo nombre.
        - Sin insumo: compara promedio de todos los insumos del proveedor vs. media global.
        - Si no hay datos suficientes: retorna 0.5 (neutro).
        """
        from django.db.models import Avg
        from insumos.models import Insumo as InsumoModel
        try:
            if insumo is not None:
                precio_insumo = float(insumo.precio_unitario or 0)
                global_avg = (
                    InsumoModel.objects
                    .filter(nombre=insumo.nombre, proveedor__activo=True)
                    .aggregate(avg=Avg('precio_unitario'))['avg']
                )
                if not global_avg or global_avg == 0:
                    return 0.5
                return min(1.0, max(0.0, precio_insumo / (float(global_avg) * 2)))
            else:
                proveedor_avg = (
                    InsumoModel.objects
                    .filter(proveedor=proveedor)
                    .aggregate(avg=Avg('precio_unitario'))['avg']
                )
                global_avg = (
                    InsumoModel.objects
                    .filter(proveedor__activo=True)
                    .aggregate(avg=Avg('precio_unitario'))['avg']
                )
                if not proveedor_avg or not global_avg or global_avg == 0:
                    return 0.5
                return min(1.0, max(0.0, float(proveedor_avg) / (float(global_avg) * 2)))
        except Exception:
            return 0.5

    def _cumplimiento(self, proveedor) -> float:
        """Proporción de órdenes confirmadas. Sin historial → 1.0 (beneficio de la duda)."""
        from pedidos.models import OrdenCompra
        ordenes = OrdenCompra.objects.filter(proveedor=proveedor)
        total = ordenes.count()
        if total == 0:
            return 1.0
        return ordenes.filter(estado='confirmada').count() / total

    def _incidencias(self, proveedor) -> float:
        """Proporción de órdenes rechazadas. Sin historial → 0.0 (sin incidencias conocidas)."""
        from pedidos.models import OrdenCompra
        ordenes = OrdenCompra.objects.filter(proveedor=proveedor)
        total = ordenes.count()
        if total == 0:
            return 0.0
        return ordenes.filter(estado='rechazada').count() / total

    def _disponibilidad(self, proveedor, insumo=None) -> float:
        """
        Proporción de consultas de stock con resultado positivo (últimas 10).
        Sin historial → 1.0 (asumir disponible).
        """
        from automatizacion.models import ConsultaStockProveedor
        qs = ConsultaStockProveedor.objects.filter(proveedor=proveedor)
        if insumo is not None:
            qs = qs.filter(insumo=insumo)
        qs = qs.order_by('-creado')[:10]
        if not qs.exists():
            return 1.0
        positivas = qs.filter(estado__in=['disponible', 'parcial']).count()
        return positivas / qs.count()

    # ------------------------------------------------------------------ #
    # Score ponderado                                                      #
    # ------------------------------------------------------------------ #

    def calcular_score(self, proveedor, insumo=None) -> float:
        """Score ponderado [0, 100]. Mayor es mejor."""
        pesos = self._get_pesos()
        precio = self._precio_relativo(proveedor, insumo)
        cumplimiento = self._cumplimiento(proveedor)
        incidencias = self._incidencias(proveedor)
        disponibilidad = self._disponibilidad(proveedor, insumo)
        score = (
            pesos['precio'] * (1 - precio) +
            pesos['cumplimiento'] * cumplimiento +
            pesos['incidencias'] * (1 - incidencias) +
            pesos['disponibilidad'] * disponibilidad
        )
        return round(score * 100, 2)

    # ------------------------------------------------------------------ #
    # Recomendación                                                        #
    # ------------------------------------------------------------------ #

    def recomendar(self, insumo=None):
        """
        Calcula el score de todos los proveedores activos, persiste en ScoreProveedor
        y retorna (mejor_proveedor, score).
        """
        from proveedores.models import Proveedor
        from automatizacion.models import ScoreProveedor
        from django.utils import timezone
        mejor = None
        mejor_score = -1.0
        for p in Proveedor.objects.filter(activo=True):
            score = self.calcular_score(p, insumo)
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
