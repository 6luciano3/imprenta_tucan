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
    # Umbral para R1: stock <= este valor → sin_stock_critico (alta)
    'DEMANDA_UMBRAL_CRITICO': 0,
    # Factor para R3: stock < demanda × factor → compra_preventiva (media)
    'DEMANDA_FACTOR_PREVENTIVO': 1.0,
    # Umbral para R4: pedidos retrasados > este valor → alerta_retraso (alta)
    'DEMANDA_UMBRAL_RETRASO': 3,

    # --- Caps de sanity para imprenta PYME (evitan que datos de semilla inflen sugerencias) ---
    # Techo de consumo mensual por insumo cuando no hay historial real
    'DEMANDA_CAP_MENSUAL_MAX': 100,
    # Piso mínimo de referencia mensual cuando stock_actual es 0
    'DEMANDA_CAP_MENSUAL_PISO': 5,
    # La demanda ajustada cap = ref_mensual × este factor (default 2 = 2 meses de stock)
    'DEMANDA_CAP_FACTOR_DEMANDA': 2,
    # stock_minimo_efectivo cap = demanda_ajustada × este factor (default 1.5 = 6 semanas)
    'DEMANDA_CAP_FACTOR_STOCK_MIN': 1.5,

    # --- Tabla de Proyección Demanda (dashboard) ---
    'PROYECCION_N_INSUMOS': 8,             # cantidad de insumos a mostrar en la tabla
    'PROYECCION_MESES': 3,                  # ventana de meses para media móvil (fuente 2)
    'PROYECCION_MESES_ETS': 12,             # períodos históricos para modelo ETS
    'TOP_N_PROVEEDORES_COTIZACION': 3,      # proveedores rankeados para SC automática

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
