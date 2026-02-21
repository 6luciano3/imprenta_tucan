from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import ComboOferta, ComboOfertaProducto
from .serializers import ComboOfertaSerializer

class ComboOfertaViewSet(viewsets.ModelViewSet):
    queryset = ComboOferta.objects.all()
    serializer_class = ComboOfertaSerializer

    @action(detail=True, methods=['post'])
    def enviar(self, request, pk=None):
        combo = self.get_object()
        combo.enviada = True
        combo.fecha_envio = timezone.now()
        combo.save()
        return Response({'status': 'oferta enviada'})

    @action(detail=True, methods=['post'])
    def responder(self, request, pk=None):
        combo = self.get_object()
        respuesta = request.data.get('respuesta')
        combo.fecha_respuesta = timezone.now()
        if respuesta == 'aceptar':
            combo.aceptada = True
            combo.rechazada = False
        elif respuesta == 'rechazar':
            combo.aceptada = False
            combo.rechazada = True
        combo.save()
        return Response({'status': f'oferta {respuesta}'})
