from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from automatizacion.models_feedback import FeedbackRecomendacion
from pedidos.models import Pedido
from proveedores.models import Proveedor
from insumos.models import Insumo
from .services import ProveedorInteligenteService
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .services import CRITERIOS_PESOS

User = get_user_model()


@method_decorator(csrf_exempt, name='dispatch')
class FeedbackRecomendacionAPIView(APIView):
    def post(self, request):
        data = request.data
        pedido_id = data.get('pedido_id')
        proveedor_recomendado_id = data.get('proveedor_recomendado_id')
        proveedor_final_id = data.get('proveedor_final_id')
        insumo_id = data.get('insumo_id')
        decision = data.get('decision')
        comentario = data.get('comentario', '')
        feedback = {
            'precio': float(data.get('feedback_precio', 0)),
            'cumplimiento': float(data.get('feedback_cumplimiento', 0)),
            'incidencias': float(data.get('feedback_incidencias', 0)),
            'disponibilidad': float(data.get('feedback_disponibilidad', 0)),
        }
        user = request.user if request.user.is_authenticated else None
        try:
            pedido = Pedido.objects.get(pk=pedido_id)
            proveedor_recomendado = Proveedor.objects.get(pk=proveedor_recomendado_id)
            proveedor_final = Proveedor.objects.get(pk=proveedor_final_id)
            insumo = Insumo.objects.get(pk=insumo_id)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        FeedbackRecomendacion.objects.create(
            pedido=pedido,
            proveedor_recomendado=proveedor_recomendado,
            proveedor_final=proveedor_final,
            insumo=insumo,
            usuario=user,
            decision=decision,
            comentario=comentario,
            feedback_precio=feedback['precio'],
            feedback_cumplimiento=feedback['cumplimiento'],
            feedback_incidencias=feedback['incidencias'],
            feedback_disponibilidad=feedback['disponibilidad'],
        )
        # Actualizar pesos de criterios
        ProveedorInteligenteService.actualizar_pesos_feedback(feedback)
        return Response({'mensaje': 'Feedback registrado y sistema actualizado.'})


@method_decorator(csrf_exempt, name='dispatch')
class CriteriosPesosAPIView(APIView):
    def get(self, request):
        # Devuelve los pesos actuales de criterios para autocompletar el formulario
        return Response({
            'precio': CRITERIOS_PESOS.get('precio', 0),
            'cumplimiento': CRITERIOS_PESOS.get('cumplimiento', 0),
            'incidencias': CRITERIOS_PESOS.get('incidencias', 0),
            'disponibilidad': CRITERIOS_PESOS.get('disponibilidad', 0),
        })
