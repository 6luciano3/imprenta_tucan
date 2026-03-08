from rest_framework import mixins
from rest_framework import routers, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from automatizacion.models import RankingCliente, ScoreProveedor, OrdenSugerida, OfertaAutomatica, AprobacionAutomatica, AutomationLog
from django.contrib.auth import get_user_model
from utils.automationlog_utils import registrar_automation_log
from automatizacion.api.services import ProveedorInteligenteService
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
    proveedor_cuit = serializers.SerializerMethodField()
    proveedor_rubro = serializers.SerializerMethodField()
    cumplimiento = serializers.SerializerMethodField()
    incidencias = serializers.SerializerMethodField()
    ordenes_90d = serializers.SerializerMethodField()
    volumen_90d = serializers.SerializerMethodField()
    ultima_actividad = serializers.SerializerMethodField()

    class Meta:
        model = ScoreProveedor
        fields = '__all__'
        extra_fields = [
            'proveedor_nombre', 'proveedor_cuit', 'proveedor_rubro',
            'cumplimiento', 'incidencias', 'ordenes_90d', 'volumen_90d', 'ultima_actividad'
        ]

    def get_proveedor_nombre(self, obj):
        # Devuelve el nombre del proveedor relacionado
        return getattr(obj.proveedor, 'nombre', None)

    def get_proveedor_cuit(self, obj):
        return getattr(obj.proveedor, 'cuit', None)

    def get_proveedor_rubro(self, obj):
        return getattr(obj.proveedor, 'rubro', None)

    def get_cumplimiento(self, obj):
        total = getattr(obj, '_ordenes_90d', None) or 0
        if not total:
            return 0.0
        return round((getattr(obj, '_confirmadas_90d', 0) or 0) / total * 100.0, 2)

    def get_incidencias(self, obj):
        total = getattr(obj, '_ordenes_90d', None) or 0
        if not total:
            return 0.0
        return round((getattr(obj, '_rechazadas_90d', 0) or 0) / total * 100.0, 2)

    def get_ordenes_90d(self, obj):
        return getattr(obj, '_ordenes_90d', 0) or 0

    def get_volumen_90d(self, obj):
        return getattr(obj, '_volumen_90d', 0) or 0

    def get_ultima_actividad(self, obj):
        val = getattr(obj, '_ultima_actividad_90d', None)
        return val.isoformat() if val else None


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
        # Solo lectura: retorna el ranking precalculado por la tarea Celery.
        # Si la tabla está vacía se devuelve un queryset vacío; el seed se realiza
        # llamando a POST /api/.../ranking/seed/ o ejecutando tarea_ranking_clientes.
        return (
            RankingCliente.objects.select_related('cliente')
            .order_by('-score')[:10]
        )

    @action(detail=False, methods=['post'])
    def seed(self, request):
        """Dispara el recálculo inicial del ranking (solo si la tabla está vacía)."""
        if RankingCliente.objects.exists():
            return Response({'detail': 'El ranking ya tiene datos.'}, status=200)
        try:
            from core.ai_ml.ranking import calcular_ranking_clientes
            resultado = calcular_ranking_clientes()
            return Response(resultado, status=201)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class ScoreProveedorViewSet(viewsets.ModelViewSet):
    queryset = ScoreProveedor.objects.all()
    serializer_class = ScoreProveedorSerializer
    http_method_names = ['get', 'head', 'options']  # Solo lectura

    def get_queryset(self):
        from django.db.models import Count, Sum, Max, Q
        from django.utils import timezone
        from datetime import timedelta

        # Seeding inicial: solo si la tabla está completamente vacía (seed único)
        if not ScoreProveedor.objects.exists():
            from proveedores.models import Proveedor
            from core.motor.proveedor_engine import ProveedorInteligenteEngine
            engine = ProveedorInteligenteEngine()
            for proveedor in Proveedor.objects.filter(activo=True):
                score = engine.calcular_score(proveedor, insumo=None)
                ScoreProveedor.objects.update_or_create(
                    proveedor=proveedor,
                    defaults={'score': score}
                )

        desde = timezone.now() - timedelta(days=90)
        return (
            ScoreProveedor.objects
            .select_related('proveedor')
            .annotate(
                _ordenes_90d=Count(
                    'proveedor__ordencompra',
                    filter=Q(proveedor__ordencompra__fecha_creacion__gte=desde),
                ),
                _confirmadas_90d=Count(
                    'proveedor__ordencompra',
                    filter=Q(
                        proveedor__ordencompra__fecha_creacion__gte=desde,
                        proveedor__ordencompra__estado='confirmada',
                    ),
                ),
                _rechazadas_90d=Count(
                    'proveedor__ordencompra',
                    filter=Q(
                        proveedor__ordencompra__fecha_creacion__gte=desde,
                        proveedor__ordencompra__estado='rechazada',
                    ),
                ),
                _volumen_90d=Sum(
                    'proveedor__ordencompra__cantidad',
                    filter=Q(proveedor__ordencompra__fecha_creacion__gte=desde),
                    default=0,
                ),
                _ultima_actividad_90d=Max(
                    'proveedor__ordencompra__fecha_creacion',
                    filter=Q(proveedor__ordencompra__fecha_creacion__gte=desde),
                ),
            )
        )


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

    @action(detail=False, methods=['get', 'post'])
    def demo(self, request):
        """Genera 3 eventos de demo para validar el panel de logs."""
        User = get_user_model()
        usuario = User.objects.filter(is_superuser=True).first()

        registrar_automation_log(
            'DEMO_RANKING',
            'Se ejecutó ranking de clientes (demo).',
            usuario=usuario,
            datos={'source': 'demo', 'modulo': 'ranking_clientes'}
        )

        registrar_automation_log(
            'DEMO_OFERTAS',
            'Se generaron ofertas automáticas (demo).',
            usuario=usuario,
            datos={'source': 'demo', 'modulo': 'ofertas_automaticas', 'count': 2}
        )

        registrar_automation_log(
            'DEMO_APROBACION',
            'Se aprobó automáticamente un pedido (demo).',
            usuario=usuario,
            datos={'source': 'demo', 'modulo': 'aprobaciones', 'pedido_id': 0, 'aprobado': True}
        )

        return Response({'created': 3})


router = routers.DefaultRouter()
router.register(r'clientes/ranking', RankingClienteViewSet, basename='clientes-ranking')
router.register(r'score-proveedores', ScoreProveedorViewSet)
router.register(r'ordenes-sugeridas', OrdenSugeridaViewSet)
router.register(r'ofertas-automaticas', OfertaAutomaticaViewSet)
router.register(r'aprobaciones-automaticas', AprobacionAutomaticaViewSet)
router.register(r'automation-logs', AutomationLogViewSet)
