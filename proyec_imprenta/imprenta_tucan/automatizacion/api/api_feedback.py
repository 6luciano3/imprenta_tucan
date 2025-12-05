from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from automatizacion.models_feedback import FeedbackRecomendacion
from pedidos.models import Pedido
from proveedores.models import Proveedor
from insumos.models import Insumo
from .services import ProveedorInteligenteService
from django.contrib.auth import get_user_model

User = get_user_model()


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
            pedido = Pedido.objects.get(id=pedido_id)
            proveedor_recomendado = Proveedor.objects.get(id=proveedor_recomendado_id)
            proveedor_final = Proveedor.objects.get(id=proveedor_final_id)
            insumo = Insumo.objects.get(id=insumo_id)
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
