"""
Motor de Procesos Inteligentes — Imprenta Tucan
================================================

Facade central que unifica los tres procesos inteligentes del sistema.

Procesos disponibles:
    'clientes'    → PI-1: Ranking multicriterio + ofertas segmentadas
    'proveedores' → PI-2: Score ponderado persistente + recomendación
    'demanda'     → PI-3: Predicción por media móvil + motor de reglas

Uso rápido:
    from core.motor import MotorProcesosInteligentes

    # Ejecutar un proceso
    resultado = MotorProcesosInteligentes.ejecutar('clientes')

    # Ejecutar todos
    resultados = MotorProcesosInteligentes.ejecutar_todos()

    # Incorporar retroalimentación
    MotorProcesosInteligentes.retroalimentar('proveedores', {
        'precio': +0.05, 'cumplimiento': -0.03,
        'incidencias': 0.0, 'disponibilidad': -0.02,
    })
"""

from .base import ProcesoInteligenteBase
from .config import MotorConfig
from .cliente_engine import ClienteInteligenteEngine
from .proveedor_engine import ProveedorInteligenteEngine
from .demanda_engine import DemandaInteligenteEngine


class MotorProcesosInteligentes:
    """
    Facade que coordina los tres motores inteligentes.

    Todos los métodos son classmethod para uso conveniente sin instanciar.
    """

    ENGINES: dict = {
        'clientes': ClienteInteligenteEngine,
        'proveedores': ProveedorInteligenteEngine,
        'demanda': DemandaInteligenteEngine,
    }

    @classmethod
    def ejecutar(cls, proceso: str, **kwargs) -> dict:
        """
        Ejecuta el proceso indicado.

        Args:
            proceso: 'clientes' | 'proveedores' | 'demanda'
            **kwargs: parámetros opcionales pasados al motor (ej. insumo=<Insumo>)

        Retorna dict con 'estado': 'ok' | 'error'.
        """
        engine_cls = cls.ENGINES.get(proceso)
        if engine_cls is None:
            return {
                'estado': 'error',
                'detalle': f"Proceso '{proceso}' no encontrado. Opciones: {list(cls.ENGINES)}",
            }
        return engine_cls().ejecutar(**kwargs)

    @classmethod
    def ejecutar_todos(cls) -> dict:
        """
        Ejecuta los tres procesos en secuencia.

        Retorna:
            {
                'clientes': { ... },
                'proveedores': { ... },
                'demanda': { ... },
            }
        """
        resultados = {}
        for nombre, engine_cls in cls.ENGINES.items():
            try:
                resultados[nombre] = engine_cls().ejecutar()
            except Exception as e:
                resultados[nombre] = {'estado': 'error', 'detalle': str(e)}
        return resultados

    @classmethod
    def retroalimentar(cls, proceso: str, feedback: dict) -> None:
        """
        Incorpora feedback al motor del proceso indicado.

        Args:
            proceso: 'clientes' | 'proveedores' | 'demanda'
            feedback: dict específico para cada motor (ver docstring de cada engine)
        """
        engine_cls = cls.ENGINES.get(proceso)
        if engine_cls:
            engine_cls().retroalimentar(feedback)

    @classmethod
    def estado(cls) -> dict:
        """
        Retorna un resumen de la configuración actual de cada motor
        (pesos, parámetros activos).
        """
        return {
            'proveedores': {
                'pesos': ProveedorInteligenteEngine()._get_pesos(),
            },
            'demanda': {
                'meses_historico': MotorConfig.get('DEMANDA_MESES_HISTORICO', cast=int),
                'umbral_precio_critico': MotorConfig.get('INSUMO_CRITICO_UMBRAL_PRECIO', cast=float),
            },
            'clientes': {
                'ventana_dias': MotorConfig.get('RANKING_VENTANA_DIAS', cast=int),
                'periodicidad': MotorConfig.get('RANKING_PERIODICIDAD'),
            },
        }
