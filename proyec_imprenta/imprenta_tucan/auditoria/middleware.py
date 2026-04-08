from contextvars import ContextVar

# M-11: reemplazado threading.local por contextvars.ContextVar para compatibilidad
# con ASGI / async workers. ContextVar mantiene un valor distinto por tarea async,
# lo que evita fugas de request entre corutinas concurrentes.
_current_request: ContextVar = ContextVar('current_request', default=None)


def get_current_request():
    return _current_request.get()


def get_current_user():
    req = get_current_request()
    if req is not None and hasattr(req, 'user'):
        try:
            if req.user.is_authenticated:
                return req.user
        except Exception:
            pass
    return None


class AuditMiddleware:
    """Guarda el request actual en ContextVar para que las señales puedan leer usuario/IP.
    Compatible con WSGI y ASGI (async workers).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _current_request.set(request)
        try:
            response = self.get_response(request)
        finally:
            _current_request.reset(token)
        return response
