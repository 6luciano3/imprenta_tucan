from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from insumos.models import Insumo
from pedidos.models import OrdenCompra
from proveedores.models import Proveedor
from .services import ProveedorInteligenteService
from django.utils import timezone


class OrdenCompraAutomaticaAPIView(APIView):
    def post(self, request):
        insumo_id = request.data.get('insumo_id')
        cantidad = request.data.get('cantidad')
        if not insumo_id or not cantidad:
            return Response({'error': 'insumo_id y cantidad son requeridos'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            insumo = Insumo.objects.get(id=insumo_id)
        except Insumo.DoesNotExist:
            return Response({'error': 'Insumo no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        proveedor = ProveedorInteligenteService.recomendar_proveedor(insumo)
        if not proveedor:
            return Response({'error': 'No se encontró proveedor recomendado'}, status=status.HTTP_404_NOT_FOUND)

        # Generar orden de compra en estado "sugerida"
        orden = OrdenCompra.objects.create(
            insumo=insumo,
            proveedor=proveedor,
            cantidad=int(cantidad),
            estado='sugerida',
            comentario='Generada automáticamente desde API'
        )

        # Simular consulta de stock (en un sistema real, aquí se enviaría la consulta al proveedor)
        stock_disponible = 100  # Simulación
        if int(cantidad) <= stock_disponible:
            disponibilidad = 'Disponible'
        elif stock_disponible > 0:
            disponibilidad = 'Parcial'
        else:
            disponibilidad = 'No disponible'

        # Registrar respuesta y devolver al admin
        # Notificar al proveedor por email
        email_ok, email_error = False, 'no intentado'
        try:
            from automatizacion.services import enviar_email_orden_compra_proveedor
            email_ok, email_error = enviar_email_orden_compra_proveedor(orden)
        except Exception as e:
            email_error = str(e)

        return Response({
            'orden_id': orden.id,
            'proveedor_id': proveedor.id,
            'proveedor_nombre': proveedor.nombre,
            'disponibilidad': disponibilidad,
            'email_proveedor_enviado': email_ok,
            'email_proveedor_error': email_error if not email_ok else None,
            'mensaje': 'Orden de compra sugerida y consulta de stock realizada.'
        })
