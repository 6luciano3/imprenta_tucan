from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from insumos.models import Insumo
from .services import ProveedorInteligenteService
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from proveedores.models import Proveedor


@method_decorator(csrf_exempt, name='dispatch')
class RecomendacionProveedorAPIView(APIView):
    def post(self, request):
        insumo_id = request.data.get('insumo_id')
        if not insumo_id:
            return Response({'error': 'insumo_id es requerido'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            insumo = Insumo.objects.get(pk=insumo_id)
        except Insumo.DoesNotExist:
            return Response({'error': 'Insumo no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        proveedor = ProveedorInteligenteService.recomendar_proveedor(insumo)
        # Fallback: si no hay recomendación, usar el proveedor del insumo o el primero activo
        if not proveedor:
            if getattr(insumo, 'proveedor', None):
                proveedor = insumo.proveedor
            else:
                proveedor = Proveedor.objects.filter(activo=True).order_by('nombre').first()
            if not proveedor:
                return Response({'error': 'No hay proveedores disponibles'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'proveedor_id': proveedor.id,
            'proveedor_nombre': proveedor.nombre,
            'mensaje': 'Proveedor recomendado exitosamente'
        })
