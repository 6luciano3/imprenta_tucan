import threading

_local = threading.local()


def get_current_request():
    return getattr(_local, 'request', None)


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
    """Guarda el request actual en thread-local para que las señales puedan leer usuario/IP."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.request = request
        try:
            response = self.get_response(request)
        finally:
            # evitar fugas entre requests
            _local.request = None
        return response
