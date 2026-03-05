"""
PI-1 — Motor Inteligente de Clientes.

Pipeline:
    1. Calcula score ponderado por datos históricos (ventas, frecuencia, margen,
       consumo crítico). Pesos configurables desde BD.
    2. Clasifica clientes en tiers: Premium / Estratégico / Estándar / Nuevo.
    3. Genera combos personalizados con filtrado colaborativo.
    4. Retroalimenta el score cuando el cliente acepta/rechaza una oferta.
"""
from .base import ProcesoInteligenteBase


class ClienteInteligenteEngine(ProcesoInteligenteBase):
    nombre = "clientes"

    def ejecutar(self, **kwargs) -> dict:
        """
        Ejecuta el ciclo completo:
            1. Recalcula ranking multicriterio de todos los clientes.
            2. Genera ofertas segmentadas por tier.

        Retorna:
            {
                'estado': 'ok',
                'ranking': <resultado de tarea_ranking_clientes>,
                'ofertas': <resultado de tarea_generar_ofertas>,
            }
        """
        try:
            # Importación diferida para evitar problemas con Django setup
            from automatizacion.tasks import tarea_ranking_clientes, tarea_generar_ofertas
            res_ranking = tarea_ranking_clientes()
            res_ofertas = tarea_generar_ofertas()
            return {
                'estado': 'ok',
                'ranking': res_ranking,
                'ofertas': res_ofertas,
            }
        except Exception as e:
            return {'estado': 'error', 'detalle': str(e)}

    def retroalimentar(self, feedback: dict) -> None:
        """
        Ajusta el score del cliente según su respuesta a una oferta.

        feedback esperado:
            {'cliente_id': int, 'accion': 'aceptar' | 'rechazar'}

        Ajuste: aceptar → +3 pts | rechazar → -1 pt (clamped [0, 100]).
        El recálculo completo ocurre en el ciclo periódico de tarea_ranking_clientes.
        """
        cliente_id = feedback.get('cliente_id')
        accion = feedback.get('accion')
        if not cliente_id or accion not in ('aceptar', 'rechazar'):
            return
        try:
            from automatizacion.models import RankingCliente
            from clientes.models import Cliente
            delta = 3.0 if accion == 'aceptar' else -1.0
            rc = RankingCliente.objects.filter(cliente_id=cliente_id).first()
            if rc:
                rc.score = max(0.0, min(100.0, (rc.score or 0) + delta))
                rc.save(update_fields=['score'])
                Cliente.objects.filter(id=cliente_id).update(puntaje_estrategico=rc.score)
        except Exception:
            pass
