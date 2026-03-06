"""
Configuración centralizada del Motor de Procesos Inteligentes.

Lee valores desde la BD (Parametro / ProveedorParametro) con fallback a defaults.
Permite modificar el comportamiento del motor sin desplegar código.
"""

# Valores por defecto — se usan cuando la BD no tiene el parámetro
DEFAULTS = {
    # --- Ranking de Clientes ---
    # Los cinco pesos deben sumar 100 (se usan como porcentajes enteros).
    # Distribución: valor_total=30, margen=25, cantidad=20, frecuencia=15, critico=10 → total=100
    'RANKING_VENTANA_DIAS': 365,
    'RANKING_PESO_VALOR_TOTAL': 30,
    'RANKING_PESO_CANTIDAD': 20,
    'RANKING_PESO_FRECUENCIA': 15,
    'RANKING_PESO_CONSUMO_CRITICO': 10,
    'RANKING_PESO_MARGEN': 25,
    'RANKING_PERIODICIDAD': 'mensual',

    # --- Proceso de Proveedores ---
    'PESO_PRECIO': 0.4,
    'PESO_CUMPLIMIENTO': 0.3,
    'PESO_INCIDENCIAS': 0.2,
    'PESO_DISPONIBILIDAD': 0.1,

    # --- Predicción de Demanda ---
    'DEMANDA_MESES_HISTORICO': 3,
    'INSUMO_CRITICO_UMBRAL_PRECIO': 500.0,
    'STOCK_MINIMO_GLOBAL': 10,

    # --- Temporización / Latencia de Proveedores ---
    # lambda para decaimiento exponencial en cumplimiento/incidencias (por día)
    'CUMPLIMIENTO_DECAY_LAMBDA': 0.01,
    # ventana de tiempo para consultas de stock (días)
    'DISPONIBILIDAD_DIAS': 90,
    # días máximos esperados de respuesta del proveedor (normaliza latencia)
    'LATENCIA_MAX_DIAS': 30.0,
    # peso del criterio latencia en el score final
    'PESO_LATENCIA': 0.1,
}


class MotorConfig:
    """
    Lee configuración desde BD (Parametro o ProveedorParametro), con fallback a DEFAULTS.

    Uso:
        MotorConfig.get('PESO_PRECIO', cast=float)    # → 0.4
        MotorConfig.get('RANKING_PERIODICIDAD')        # → 'mensual'
        MotorConfig.set_proveedor('PESO_PRECIO', 0.35) # persiste en ProveedorParametro
    """

    @classmethod
    def get(cls, clave: str, cast=None):
        """Obtiene un parámetro de configuración. Intenta BD primero, luego defaults."""
        default = DEFAULTS.get(clave)
        valor = None

        # 1) Intentar desde configuracion.models.Parametro
        try:
            from configuracion.models import Parametro
            valor = Parametro.get(clave, None)
        except Exception:
            pass

        # 2) Intentar desde proveedores.models.ProveedorParametro
        if valor is None:
            try:
                from proveedores.services import get_parametro
                valor = get_parametro(clave, None)
            except Exception:
                pass

        if valor is None:
            return default

        if cast is not None:
            try:
                return cast(valor)
            except Exception:
                return default

        return valor

    @classmethod
    def set_proveedor(cls, clave: str, valor) -> None:
        """Persiste un parámetro en ProveedorParametro (sobrevive reinicios)."""
        try:
            from proveedores.models import ProveedorParametro
            ProveedorParametro.objects.update_or_create(
                clave=clave,
                defaults={'valor': str(valor), 'activo': True},
            )
        except Exception:
            pass
