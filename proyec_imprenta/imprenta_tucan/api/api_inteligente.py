from rest_framework import mixins
from rest_framework import routers, serializers, viewsets
from automatizacion.models import RankingCliente, ScoreProveedor, OrdenSugerida, OfertaAutomatica, AprobacionAutomatica, AutomationLog
from clientes.models import Cliente
from pedidos.models import Pedido, EstadoPedido


class RankingClienteSerializer(serializers.ModelSerializer):
    nombre = serializers.SerializerMethodField()
    apellido = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    telefono = serializers.SerializerMethodField()
    estado = serializers.SerializerMethodField()

    class Meta:
        model = RankingCliente
        fields = '__all__'
        extra_fields = ['nombre', 'apellido', 'email', 'telefono', 'estado']

    def get_nombre(self, obj):
        return getattr(obj.cliente, 'nombre', None)

    def get_apellido(self, obj):
        return getattr(obj.cliente, 'apellido', None)

    def get_email(self, obj):
        return getattr(obj.cliente, 'email', None)

    def get_telefono(self, obj):
        return getattr(obj.cliente, 'telefono', None)

    def get_estado(self, obj):
        return getattr(obj.cliente, 'estado', None)


class ScoreProveedorSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.SerializerMethodField()

    class Meta:
        model = ScoreProveedor
        fields = '__all__'
        extra_fields = ['proveedor_nombre']

    def get_proveedor_nombre(self, obj):
        # Devuelve el nombre del proveedor relacionado
        return getattr(obj.proveedor, 'nombre', None)


class OrdenSugeridaSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrdenSugerida
        fields = '__all__'


class OfertaAutomaticaSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfertaAutomatica
        fields = '__all__'


class AprobacionAutomaticaSerializer(serializers.ModelSerializer):
    class Meta:
        model = AprobacionAutomatica
        fields = '__all__'


class AutomationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationLog
        fields = '__all__'


# Solo clientes destacados: top 5 por score


class RankingClienteViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = RankingClienteSerializer
    queryset = RankingCliente.objects.all()  # Necesario para DRF router

    def get_queryset(self):
        # Top 10 clientes con score > 50
        destacados = list(RankingCliente.objects.select_related('cliente').filter(score__gt=50).order_by('-score')[:10])
        if destacados:
            return destacados
        # Si no hay destacados, buscar los 10 primeros clientes con pedidos pendientes
        # Consideramos 'Pendiente' como estado de pedido pendiente
        estado_pendiente = EstadoPedido.objects.filter(nombre__iexact='pendiente').first()
        if estado_pendiente:
            clientes_pendientes_ids = Pedido.objects.filter(
                estado=estado_pendiente).values_list('cliente_id', flat=True).distinct()[:10]
        else:
            # Si no existe el estado 'Pendiente', tomar los 10 primeros clientes con cualquier pedido
            clientes_pendientes_ids = Pedido.objects.values_list('cliente_id', flat=True).distinct()[:10]
        clientes = Cliente.objects.filter(id__in=clientes_pendientes_ids)
        # Creamos objetos simulados de RankingCliente para compatibilidad con el serializer

        class FakeRanking:
            def __init__(self, cliente):
                self.cliente = cliente
                self.score = None
                self.actualizado = None
            # Para compatibilidad con el serializer

            @property
            def estado(self):
                return getattr(self.cliente, 'estado', None)
        return [FakeRanking(c) for c in clientes]


class ScoreProveedorViewSet(viewsets.ModelViewSet):
    queryset = ScoreProveedor.objects.all()
    serializer_class = ScoreProveedorSerializer


class OrdenSugeridaViewSet(viewsets.ModelViewSet):
    queryset = OrdenSugerida.objects.all()
    serializer_class = OrdenSugeridaSerializer


class OfertaAutomaticaViewSet(viewsets.ModelViewSet):
    queryset = OfertaAutomatica.objects.all()
    serializer_class = OfertaAutomaticaSerializer


class AprobacionAutomaticaViewSet(viewsets.ModelViewSet):
    queryset = AprobacionAutomatica.objects.all()
    serializer_class = AprobacionAutomaticaSerializer


class AutomationLogViewSet(viewsets.ModelViewSet):
    queryset = AutomationLog.objects.all()
    serializer_class = AutomationLogSerializer


router = routers.DefaultRouter()
router.register(r'clientes/ranking', RankingClienteViewSet, basename='clientes-ranking')
router.register(r'score-proveedores', ScoreProveedorViewSet)
router.register(r'ordenes-sugeridas', OrdenSugeridaViewSet)
router.register(r'ofertas-automaticas', OfertaAutomaticaViewSet)
router.register(r'aprobaciones-automaticas', AprobacionAutomaticaViewSet)
router.register(r'automation-logs', AutomationLogViewSet)
