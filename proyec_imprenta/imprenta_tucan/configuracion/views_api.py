import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from configuracion.utils.safe_eval import safe_eval

@csrf_exempt
def formula_validate_api(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
        expresion = data.get('expresion')
        variables = data.get('variables', {})
        resultado = safe_eval(expresion, variables)
        return JsonResponse({'ok': True, 'resultado': resultado})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
