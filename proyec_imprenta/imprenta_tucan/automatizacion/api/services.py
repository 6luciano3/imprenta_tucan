from proveedores.models import Proveedor
from insumos.models import Insumo
from pedidos.models import Pedido
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
        # Normalizado: menor precio es mejor (0 a 1)
        precios = Pedido.objects.filter(proveedor=proveedor, insumo=insumo).values_list('precio_unitario', flat=True)
        if not precios:
            return 1
        min_precio = min(precios)
        max_precio = max(precios)
        actual = precios[-1]
        if max_precio == min_precio:
            return 1
        return (max_precio - actual) / (max_precio - min_precio)

    @staticmethod
    def _cumplimiento(proveedor):
        pedidos = Pedido.objects.filter(proveedor=proveedor)
        if not pedidos:
            return 1
        cumplidos = pedidos.filter(entregado_a_tiempo=True).count()
        return cumplidos / pedidos.count()

    @staticmethod
    def _incidencias(proveedor):
        pedidos = Pedido.objects.filter(proveedor=proveedor)
        if not pedidos:
            return 0
        con_incidencias = pedidos.filter(incidencia=True).count()
        return con_incidencias / pedidos.count()

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
