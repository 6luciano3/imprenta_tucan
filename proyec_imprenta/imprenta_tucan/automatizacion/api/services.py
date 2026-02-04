from proveedores.models import Proveedor
from insumos.models import Insumo
from pedidos.models import OrdenCompra
from automatizacion.models import ScoreProveedor
from django.db import transaction
from django.utils import timezone

# Parámetros iniciales de ponderación (pueden ser ajustados por feedback)
CRITERIOS_PESOS = {
    'precio': 0.4,
    'cumplimiento': 0.3,
    'incidencias': 0.2,
    'disponibilidad': 0.1,
}


class ProveedorInteligenteService:
    @staticmethod
    def calcular_score(proveedor, insumo):
        # Precio histórico promedio
        precio = ProveedorInteligenteService._precio_promedio(proveedor, insumo)
        # Cumplimiento de plazos
        cumplimiento = ProveedorInteligenteService._cumplimiento(proveedor)
        # Incidencias
        incidencias = ProveedorInteligenteService._incidencias(proveedor)
        # Disponibilidad (última consulta)
        disponibilidad = ProveedorInteligenteService._disponibilidad(proveedor, insumo)
        # Score ponderado
        score = (
            CRITERIOS_PESOS['precio'] * (1 - precio) +
            CRITERIOS_PESOS['cumplimiento'] * cumplimiento +
            CRITERIOS_PESOS['incidencias'] * (1 - incidencias) +
            CRITERIOS_PESOS['disponibilidad'] * disponibilidad
        )
        return round(score * 100, 2)

    @staticmethod
    def _precio_promedio(proveedor, insumo):
        # No hay precio_unitario en OrdenCompra: retornar neutro (1)
        # Si en el futuro se agrega precio, ajustar esta métrica.
        return 1

    @staticmethod
    def _cumplimiento(proveedor):
        # Proxy: proporción de órdenes confirmadas sobre el total
        ordenes = OrdenCompra.objects.filter(proveedor=proveedor)
        if not ordenes:
            return 1
        confirmadas = ordenes.filter(estado='confirmada').count()
        return confirmadas / ordenes.count()

    @staticmethod
    def _incidencias(proveedor):
        # Proxy: proporción de órdenes rechazadas sobre el total
        ordenes = OrdenCompra.objects.filter(proveedor=proveedor)
        if not ordenes:
            return 0
        rechazadas = ordenes.filter(estado='rechazada').count()
        return rechazadas / ordenes.count()

    @staticmethod
    def _disponibilidad(proveedor, insumo):
        # Simulación: 1 si última consulta fue positiva, 0 si no
        # Aquí deberías consultar el historial real de disponibilidad
        return 1

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
                defaults={'score': score, 'actualizado': timezone.now()}
            )
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[0][0] if scores else None

    @staticmethod
    def actualizar_pesos_feedback(feedback):
        # feedback: {'precio': +0.05, 'cumplimiento': -0.05, ...}
        for k, v in feedback.items():
            if k in CRITERIOS_PESOS:
                CRITERIOS_PESOS[k] = max(0, min(1, CRITERIOS_PESOS[k] + v))
        # Normalizar suma a 1
        total = sum(CRITERIOS_PESOS.values())
        for k in CRITERIOS_PESOS:
            CRITERIOS_PESOS[k] /= total
