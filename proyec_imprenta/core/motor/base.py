"""
Interfaz base para los Procesos Inteligentes del sistema.
Cada proceso debe implementar ejecutar() y retroalimentar().
"""
from abc import ABC, abstractmethod


class ProcesoInteligenteBase(ABC):
    """
    Contrato común para los tres motores inteligentes del sistema.

    Flujo estándar:
        1. ejecutar(**kwargs) → corre el proceso y retorna un dict con resultados.
        2. retroalimentar(feedback) → incorpora la respuesta humana/del sistema.

    El dict retornado por ejecutar() siempre incluye la clave 'estado':
        'ok'    → proceso completado sin errores.
        'error' → fallo con detalle en 'detalle'.
    """

    nombre: str = "base"

    @abstractmethod
    def ejecutar(self, **kwargs) -> dict:
        """Ejecuta el proceso principal. Retorna dict con resultados y métricas."""

    @abstractmethod
    def retroalimentar(self, feedback: dict) -> None:
        """Incorpora retroalimentación para ajustar el proceso en futuros ciclos."""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} nombre='{self.nombre}'>"
