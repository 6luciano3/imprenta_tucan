from functools import wraps
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.contrib import messages


def requiere_permiso(modulo, accion=None):
    """
    Decorador que verifica si el usuario autenticado tiene permiso
    para acceder al modulo y accion indicados.
    
    Uso:
        @requiere_permiso('Clientes')
        @requiere_permiso('Clientes', 'Crear')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Si no esta autenticado -> login
            if not request.user.is_authenticated:
                return redirect('login')
            
            # Superuser siempre tiene acceso
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Verificar que el usuario tiene rol asignado
            usuario = request.user
            if not hasattr(usuario, 'rol') or not usuario.rol:
                messages.error(request, 'No tiene un rol asignado. Contacte al administrador.')
                return redirect('dashboard')
            
            # Verificar que el rol esta activo
            if usuario.rol.estado != 'Activo':
                messages.error(request, 'Su rol esta inactivo. Contacte al administrador.')
                return redirect('dashboard')
            
            # Obtener permisos del rol
            permisos_rol = usuario.rol.permisos.filter(
                modulo__iexact=modulo
            )
            
            if not permisos_rol.exists():
                messages.error(request, f'No tiene permisos para acceder al modulo "{modulo}".')
                from django.shortcuts import render as _render
                return _render(request, '403.html', status=403)
            
            # Si se especifico una accion, verificar que este incluida
            if accion:
                tiene_accion = False
                for permiso in permisos_rol:
                    acciones = permiso.acciones if hasattr(permiso, 'acciones') else ''
                    if accion.lower() in str(acciones).lower():
                        tiene_accion = True
                        break
                if not tiene_accion:
                    messages.error(request, f'No tiene permiso para realizar la accion "{accion}" en "{modulo}".')
                    from django.shortcuts import render as _render
                    return _render(request, '403.html', status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def tiene_permiso(usuario, modulo, accion=None):
    """
    Funcion helper para verificar permisos en templates o vistas.
    Retorna True/False.
    """
    if not usuario.is_authenticated:
        return False
    if usuario.is_superuser:
        return True
    if not hasattr(usuario, 'rol') or not usuario.rol:
        return False
    if usuario.rol.estado != 'Activo':
        return False
    
    permisos_rol = usuario.rol.permisos.filter(modulo__iexact=modulo)
    if not permisos_rol.exists():
        return False
    
    if accion:
        for permiso in permisos_rol:
            acciones = permiso.acciones if hasattr(permiso, 'acciones') else ''
            if accion.lower() in str(acciones).lower():
                return True
        return False
    
    return True


class PermisosContextProcessor:
    """Context processor para hacer tiene_permiso disponible en templates."""
    
    @staticmethod
    def process(request):
        return {'tiene_permiso': lambda m, a=None: tiene_permiso(request.user, m, a)}
