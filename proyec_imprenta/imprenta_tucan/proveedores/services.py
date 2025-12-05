from .models import ProveedorParametro


def get_parametro(clave, default=None):
    try:
        param = ProveedorParametro.objects.get(clave=clave, activo=True)
        return param.valor
    except ProveedorParametro.DoesNotExist:
        return default
