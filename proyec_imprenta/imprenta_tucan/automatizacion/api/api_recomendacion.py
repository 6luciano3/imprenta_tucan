from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from insumos.models import Insumo
from .services import ProveedorInteligenteService


class RecomendacionProveedorAPIView(APIView):
    def post(self, request):
        insumo_id = request.data.get('insumo_id')
        if not insumo_id:
            return Response({'error': 'insumo_id es requerido'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            insumo = Insumo.objects.get(id=insumo_id)
        except Insumo.DoesNotExist:
            return Response({'error': 'Insumo no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        proveedor = ProveedorInteligenteService.recomendar_proveedor(insumo)
        if not proveedor:
            return Response({'error': 'No se encontró proveedor recomendado'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'proveedor_id': proveedor.id,
            'proveedor_nombre': proveedor.nombre,
            'mensaje': 'Proveedor recomendado exitosamente'
        })
