import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from configuracion.utils.safe_eval import safe_eval


@login_required
@require_POST
def formula_validate_api(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        expresion = data.get('expresion', '').strip()
        variables = data.get('variables', {})
        if not expresion:
            return JsonResponse({'ok': False, 'error': 'Expresión vacía'}, status=400)
        resultado = safe_eval(expresion, variables)
        return JsonResponse({'ok': True, 'resultado': resultado})
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Error al evaluar la expresión'}, status=400)
