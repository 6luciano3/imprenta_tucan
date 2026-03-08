class ProveedorInteligenteService:

    @staticmethod
    def _get_pesos() -> dict:
        """
        Lee pesos desde MotorConfig (misma fuente que ProveedorInteligenteEngine)
        para que CRITERIOS_PESOS persistido en CompraPropuesta coincida con los
        pesos realmente usados en el cálculo del score.
        """
        from core.motor.config import MotorConfig
        return {
            'precio': MotorConfig.get('PESO_PRECIO', cast=float),
            'cumplimiento': MotorConfig.get('PESO_CUMPLIMIENTO', cast=float),
            'incidencias': MotorConfig.get('PESO_INCIDENCIAS', cast=float),
            'disponibilidad': MotorConfig.get('PESO_DISPONIBILIDAD', cast=float),
        }

    @staticmethod
    def calcular_score(proveedor, insumo) -> float:
        """Calcula el score del proveedor delegando a PI-2 (ProveedorInteligenteEngine)."""
        from core.motor.proveedor_engine import ProveedorInteligenteEngine
        return ProveedorInteligenteEngine().calcular_score(proveedor, insumo)

    @staticmethod
    def recomendar_proveedor(insumo):
        """Recomienda el mejor proveedor activo para el insumo dado (delega a PI-2)."""
        from core.motor.proveedor_engine import ProveedorInteligenteEngine
        proveedor, _ = ProveedorInteligenteEngine().recomendar(insumo)
        return proveedor

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
