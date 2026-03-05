from proveedores.models import Proveedor
from insumos.models import Insumo
from pedidos.models import OrdenCompra
from automatizacion.models import ScoreProveedor
from django.db import transaction
from django.utils import timezone

# Pesos por defecto — sólo usados si ProveedorParametro no tiene el valor.
_PESOS_DEFAULT = {
    'precio': 0.4,
    'cumplimiento': 0.3,
    'incidencias': 0.2,
    'disponibilidad': 0.1,
}


class ProveedorInteligenteService:

    @staticmethod
    def _get_pesos() -> dict:
        """
        Lee los pesos desde ProveedorParametro (BD) para que sobrevivan
        reinicios del servidor y acumulen el feedback del administrador.
        """
        from proveedores.services import get_parametro
        pesos = {}
        for k, default in _PESOS_DEFAULT.items():
            try:
                pesos[k] = float(get_parametro(f'PESO_{k.upper()}', default))
            except Exception:
                pesos[k] = default
        return pesos

    @staticmethod
    def calcular_score(proveedor, insumo):
        precio = ProveedorInteligenteService._precio_relativo(proveedor, insumo)
        cumplimiento = ProveedorInteligenteService._cumplimiento(proveedor)
        incidencias = ProveedorInteligenteService._incidencias(proveedor)
        disponibilidad = ProveedorInteligenteService._disponibilidad(proveedor, insumo)
        pesos = ProveedorInteligenteService._get_pesos()
        score = (
            pesos['precio'] * (1 - precio) +
            pesos['cumplimiento'] * cumplimiento +
            pesos['incidencias'] * (1 - incidencias) +
            pesos['disponibilidad'] * disponibilidad
        )
        return round(score * 100, 2)

    @staticmethod
    def _precio_relativo(proveedor, insumo) -> float:
        """
        Precio relativo del proveedor en escala [0, 1].
        0 = más barato que la media; 1 = el doble de la media o más.
        Retorna 0.5 (neutro) si no hay datos suficientes.
        """
        from django.db.models import Avg
        try:
            if insumo is not None:
                precio_insumo = float(insumo.precio_unitario or 0)
                global_avg = (
                    Insumo.objects
                    .filter(nombre=insumo.nombre, proveedor__activo=True)
                    .aggregate(avg=Avg('precio_unitario'))['avg']
                )
                if not global_avg or global_avg == 0:
                    return 0.5
                return min(1.0, max(0.0, precio_insumo / (float(global_avg) * 2)))
            else:
                proveedor_avg = (
                    Insumo.objects
                    .filter(proveedor=proveedor)
                    .aggregate(avg=Avg('precio_unitario'))['avg']
                )
                global_avg = (
                    Insumo.objects
                    .filter(proveedor__activo=True)
                    .aggregate(avg=Avg('precio_unitario'))['avg']
                )
                if not proveedor_avg or not global_avg or global_avg == 0:
                    return 0.5
                return min(1.0, max(0.0, float(proveedor_avg) / (float(global_avg) * 2)))
        except Exception:
            return 0.5

    @staticmethod
    def _cumplimiento(proveedor) -> float:
        ordenes = OrdenCompra.objects.filter(proveedor=proveedor)
        total = ordenes.count()
        if total == 0:
            return 1.0  # sin historial → beneficio de la duda (perfecto)
        return ordenes.filter(estado='confirmada').count() / total

    @staticmethod
    def _incidencias(proveedor) -> float:
        ordenes = OrdenCompra.objects.filter(proveedor=proveedor)
        total = ordenes.count()
        if total == 0:
            return 0.0  # sin historial → sin incidencias conocidas
        return ordenes.filter(estado='rechazada').count() / total

    @staticmethod
    def _disponibilidad(proveedor, insumo) -> float:
        """
        Proporción de consultas de stock con resultado positivo (últimas 10).
        Retorna 1.0 (disponible) si no hay historial previo.
        """
        from automatizacion.models import ConsultaStockProveedor
        qs = ConsultaStockProveedor.objects.filter(proveedor=proveedor)
        if insumo is not None:
            qs = qs.filter(insumo=insumo)
        qs = qs.order_by('-creado')[:10]
        if not qs.exists():
            return 1.0  # sin historial → asumir disponible
        positivas = qs.filter(estado__in=['disponible', 'parcial']).count()
        return positivas / qs.count()

    @staticmethod
    @transaction.atomic
    def recomendar_proveedor(insumo):
        proveedores = Proveedor.objects.filter(activo=True)
        scores = []
        for proveedor in proveedores:
            score = ProveedorInteligenteService.calcular_score(proveedor, insumo)
            scores.append((proveedor, score))
            ScoreProveedor.objects.update_or_create(
                proveedor=proveedor,
                defaults={'score': score, 'actualizado': timezone.now()},
            )
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[0][0] if scores else None

    @staticmethod
    def actualizar_pesos_feedback(feedback: dict) -> None:
        """
        Ajusta los pesos con el delta indicado y los persiste en ProveedorParametro
        para que sobrevivan reinicios del servidor.

        feedback: {'precio': +0.05, 'cumplimiento': -0.05, ...}
        """
        from proveedores.models import ProveedorParametro
        pesos = ProveedorInteligenteService._get_pesos()
        for k, v in feedback.items():
            if k in pesos:
                pesos[k] = max(0.0, min(1.0, pesos[k] + float(v)))
        total = sum(pesos.values()) or 1.0
        for k in pesos:
            pesos[k] = round(pesos[k] / total, 4)
            ProveedorParametro.objects.update_or_create(
                clave=f'PESO_{k.upper()}',
                defaults={'valor': str(pesos[k]), 'activo': True},
            )
