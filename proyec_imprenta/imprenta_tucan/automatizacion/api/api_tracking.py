from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from automatizacion.models import EmailTracking, RespuestaCliente
from django.shortcuts import get_object_or_404


@csrf_exempt
def tracking_open(request, token):
    """Vista para tracking de apertura de email (pixel 1x1)."""
    try:
        tracking = get_object_or_404(EmailTracking, token=token)
        if tracking.estado == 'enviado':
            tracking.estado = 'abierto'
            tracking.abierto_en = timezone.now()
            tracking.save(update_fields=['estado', 'abierto_en'])
        
        tracking.abierto_en = timezone.now()
        tracking.save(update_fields=['abierto_en'])
        
        pixel = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        return HttpResponse(pixel, content_type='image/png')
    except Exception as e:
        pixel = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        return HttpResponse(pixel, content_type='image/png')


@csrf_exempt
def tracking_click(request, token):
    """Vista para tracking de clicks en botón de confirmación."""
    try:
        tracking = get_object_or_404(EmailTracking, token=token)
        
        if tracking.estado in ['enviado', 'abierto']:
            tracking.estado = 'clickeado'
            tracking.clickeado_en = timezone.now()
            tracking.save(update_fields=['estado', 'clickeado_en'])
        
        return JsonResponse({
            'status': 'ok',
            'message': 'Gracias por confirmar. Te contactaremos pronto.',
            'cliente': tracking.cliente.nombre if tracking.cliente else None,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
def tracking_unsubscribe(request, token):
    """Vista para que el cliente se desuscriba."""
    try:
        tracking = get_object_or_404(EmailTracking, token=token)
        cliente = tracking.cliente
        cliente.estado = 'Inactivo'
        cliente.save(update_fields=['estado'])
        
        return JsonResponse({
            'status': 'ok',
            'message': 'Te has desuscrito correctamente.',
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
def email_response(request):
    """
    Vista para recibir respuestas de clientes por email.
    Se configura como Reply-To en los emails enviados.
    """
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            
            from_email = data.get('from', '')
            mensaje = data.get('text', data.get('body', ''))
            
            if not from_email or not mensaje:
                return JsonResponse({'status': 'error', 'message': 'Faltan datos'}, status=400)
            
            from_email = from_email.strip()
            
            tracking = EmailTracking.objects.filter(email_enviado=from_email).order_by('-enviado_en').first()
            
            if tracking:
                tracking.estado = 'respondido'
                tracking.respondido_en = timezone.now()
                tracking.respuesta_texto = mensaje[:1000]
                tracking.save(update_fields=['estado', 'respondido_en', 'respuesta_texto'])
                
                RespuestaCliente.objects.create(
                    cliente=tracking.cliente,
                    tipo=tracking.tipo,
                    email_origen=from_email,
                    mensaje=mensaje[:2000],
                )
                
                return JsonResponse({'status': 'ok', 'message': 'Respuesta registrada'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Email no encontrado'}, status=404)
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


def tracking_stats(request, token):
    """Vista para ver estadísticas de un email enviado."""
    tracking = get_object_or_404(EmailTracking, token=token)
    
    return JsonResponse({
        'email': tracking.email_enviado,
        'cliente': tracking.cliente.nombre if tracking.cliente else None,
        'tipo': tracking.tipo,
        'estado': tracking.estado,
        'enviado_en': tracking.enviado_en.isoformat() if tracking.enviado_en else None,
        'abierto_en': tracking.abierto_en.isoformat() if tracking.abierto_en else None,
        'clickeado_en': tracking.clickeado_en.isoformat() if tracking.clickeado_en else None,
        'respondido_en': tracking.respondido_en.isoformat() if tracking.respondido_en else None,
        'respuesta': tracking.respuesta_texto[:200] if tracking.respuesta_texto else None,
    })
