"""Helpers para control de permisos por Rol.

Se basa en el modelo `Rol` que tiene una relación ManyToMany con `Permiso`.
Cada `Permiso` define un `modulo`, una lista de `acciones` y un `estado`.

Decorator principal:
    @require_perm(modulo, accion=None)
    - Verifica que el usuario esté autenticado.
    - Verifica que tenga rol asignado.
    - Verifica que exista al menos un permiso activo del módulo.
    - Si se especifica `accion`, verifica que aparezca en alguna lista de acciones
      de los permisos activos de ese módulo.
    - Admin/staff (is_staff o is_superuser) pasa siempre.
    - Si no cumple, agrega mensaje de error y redirige a 'dashboard'.
"""

from functools import wraps
from typing import Optional, Callable
from django.shortcuts import redirect
from django.contrib import messages


def _expand_action_synonyms(action: str):
    """Devuelve un set de sinónimos para la acción (case-sensitive según datos)."""
    mapping = {
        'Ver': {'Ver', 'Listar', 'Detalle'},
        'Listar': {'Listar', 'Ver'},
        'Editar': {'Editar', 'Actualizar'},
        'Eliminar': {'Eliminar', 'Borrar', 'Quitar', 'Baja', 'Desactivar'},
        'Desactivar': {'Desactivar', 'Eliminar', 'Baja'},
        'Activar': {'Activar', 'Reactivar'},
        'Crear': {'Crear', 'Alta'},
    }
    return mapping.get(action, {action})


MODULE_DEFAULT_REDIRECT = {
    'Insumos': 'lista_insumos',
    'Clientes': 'lista_clientes',
    'Productos': 'lista_productos',
    'Proveedores': 'lista_proveedores',
    'Pedidos': 'lista_pedidos',
    'Roles': 'lista_roles',
    'Permisos': 'lista_permisos',
    'Reportes': 'estadisticas:dashboard',
    'Formulas': 'lista_formulas',
}

# Acciones permitidas para el módulo formulas
FORMULAS_ACCIONES = [
    'Crear', 'Ver', 'Editar', 'Actualizar', 'Validar', 'Exportar', 'Importar', 'Desactivar'
]


def require_perm(modulo: str, accion: Optional[str] = None, redirect_to: Optional[str] = None):
    """Decorator para vistas que necesitan permisos por módulo/acción."""

    def decorator(view_func: Callable):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = getattr(request, 'user', None)
            # Autenticación básica
            if not user or not user.is_authenticated:
                messages.error(request, 'Debe iniciar sesión para acceder a esta funcionalidad.')
                return redirect('login')

            # Admin/staff pasa sin restricción
            if user.is_staff or user.is_superuser:
                return view_func(request, *args, **kwargs)

            rol = getattr(user, 'rol', None)
            if rol is None:
                messages.error(request, 'No tiene un rol asignado. Acceso denegado.')
                return redirect(redirect_to or MODULE_DEFAULT_REDIRECT.get(modulo, 'dashboard'))

            permisos_qs = rol.permisos.filter(modulo=modulo, estado='Activo')
            if not permisos_qs.exists():
                messages.error(request, f'No tiene permiso para acceder al módulo {modulo}.')
                return redirect(redirect_to or MODULE_DEFAULT_REDIRECT.get(modulo, 'dashboard'))

            if accion:
                # Chequear acción (con sinónimos) en alguna lista de acciones
                synonyms = _expand_action_synonyms(accion)

                def _match(p):
                    acciones = set(p.acciones or [])
                    return bool(acciones & synonyms)
                if not any(_match(p) for p in permisos_qs):
                    messages.error(request, f'No tiene permiso para realizar la acción "{accion}" en {modulo}.')
                    return redirect(redirect_to or MODULE_DEFAULT_REDIRECT.get(modulo, 'dashboard'))

            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def require_any(*modulos: str):
    """Decorator que permite acceso si el usuario tiene al menos un permiso activo entre los módulos listados.
    Staff/superuser pasa siempre."""
    def decorator(view_func: Callable):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = getattr(request, 'user', None)
            if not user or not user.is_authenticated:
                messages.error(request, 'Debe iniciar sesión para acceder a esta funcionalidad.')
                return redirect('login')

            if user.is_staff or user.is_superuser:
                return view_func(request, *args, **kwargs)

            rol = getattr(user, 'rol', None)
            if rol is None:
                messages.error(request, 'No tiene un rol asignado. Acceso denegado.')
                return redirect('dashboard')

            perms_modules = set(rol.permisos.filter(estado='Activo').values_list('modulo', flat=True))
            if not any(m in perms_modules for m in modulos):
                messages.error(request, 'No tiene permisos para acceder a esta funcionalidad.')
                return redirect('dashboard')

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
