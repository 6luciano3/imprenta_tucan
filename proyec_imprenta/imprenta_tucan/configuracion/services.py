
from __future__ import annotations
from typing import Any
from .models import Parametro, FeatureFlag, ListaConfig
from django.core.cache import cache
# Repository Pattern for UnidadDeMedida
from .models import UnidadDeMedida


class UnidadDeMedidaRepository:
    @staticmethod
    def get_all():
        return UnidadDeMedida.objects.filter(activo=True)

    @staticmethod
    def get_by_id(unidad_id):
        return UnidadDeMedida.objects.filter(id=unidad_id, activo=True).first()

    @staticmethod
    def create(nombre, simbolo, descripcion=""):
        unidad = UnidadDeMedida(nombre=nombre, simbolo=simbolo, descripcion=descripcion)
        unidad.save()
        return unidad

    @staticmethod
    def update(unidad_id, **kwargs):
        unidad = UnidadDeMedidaRepository.get_by_id(unidad_id)
        if unidad:
            for key, value in kwargs.items():
                setattr(unidad, key, value)
            unidad.save()
        return unidad

    @staticmethod
    def deactivate(unidad_id):
        unidad = UnidadDeMedidaRepository.get_by_id(unidad_id)
        if unidad:
            unidad.activo = False
            unidad.save()
        return unidad


def get_param(codigo: str, default: Any = None):
    """Obtiene un parámetro tipado desde caché o DB.

    Uso: get_param('PAGINACION_PAGE_SIZE', 10)
    """

    return Parametro.get(codigo, default)


def set_param(codigo: str, valor: Any, tipo: str | None = None, **meta):
    """Crea/actualiza un parámetro y refresca caché."""

    return Parametro.set(codigo, valor, tipo, **meta)


def feature_enabled(flag_code: str, default: bool = False) -> bool:
    return FeatureFlag.is_active(flag_code, default)


def get_lista_config(codigo: str, default: dict | None = None) -> dict | None:
    return ListaConfig.get(codigo, default)


def invalidate_all_param_cache():  # pragma: no cover - utilidad admin/scripts
    # En memcached/redis no podemos enumerar keys por prefijo de forma portable;
    # en local (LocMemCache) .clear() es suficiente.
    cache.clear()


def get_page_size(default: int = 10, max_size: int = 500) -> int:
    """Devuelve el tamaño de página desde parámetros con saneamiento.

    Lee el parámetro 'PAGINACION_PAGE_SIZE' (tipado) y aplica límites mínimos/máximos
    para evitar valores inválidos o excesivos.
    """
    val = Parametro.get('PAGINACION_PAGE_SIZE', default)
    try:
        size = int(val)
    except (TypeError, ValueError):
        size = default
    # Sanitizar
    if size < 1:
        size = 1
    if max_size and size > max_size:
        size = max_size
    return size
