from permisos.decorators import tiene_permiso

def permisos_context(request):
    return {'tiene_permiso': lambda m, a=None: tiene_permiso(request.user, m, a)}
