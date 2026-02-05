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

    def _ordenes_ventana(self, obj):
        from django.utils import timezone
        from datetime import timedelta
        desde = timezone.now() - timedelta(days=90)
        from pedidos.models import OrdenCompra
        return OrdenCompra.objects.filter(proveedor=obj.proveedor, fecha_creacion__gte=desde)

    def get_cumplimiento(self, obj):
        qs = self._ordenes_ventana(obj)
        total = qs.count()
        if total == 0:
            return 0.0
        confirmadas = qs.filter(estado='confirmada').count()
        return round((confirmadas / total) * 100.0, 2)

    def get_incidencias(self, obj):
        qs = self._ordenes_ventana(obj)
        total = qs.count()
        if total == 0:
            return 0.0
        rechazadas = qs.filter(estado='rechazada').count()
        return round((rechazadas / total) * 100.0, 2)

    def get_ordenes_90d(self, obj):
        return self._ordenes_ventana(obj).count()

    def get_volumen_90d(self, obj):
        from django.db.models import Sum
        agg = self._ordenes_ventana(obj).aggregate(volumen=Sum('cantidad'))
        return agg.get('volumen') or 0

    def get_ultima_actividad(self, obj):
        qs = self._ordenes_ventana(obj)
        last = qs.order_by('-fecha_creacion').values_list('fecha_creacion', flat=True).first()
        return last.isoformat() if last else None


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
        # Intentar obtener top 10 clientes con score calculado
        destacados = list(
            RankingCliente.objects.select_related('cliente')
            .order_by('-score')[:10]
        )
        if destacados:
            return destacados

        # Si la tabla está vacía, calcular y persistir ranking basado en actividad de pedidos últimos 90 días
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Sum, Count

        try:
            desde = timezone.now().date() - timedelta(days=90)
            agregados = (
                Pedido.objects.filter(fecha_pedido__gte=desde)
                .values('cliente_id')
                .annotate(total=Sum('monto_total'), cantidad=Count('id'))
            )

            if agregados:
                max_total = max(a['total'] or 0 for a in agregados) or 1
                max_cant = max(a['cantidad'] or 0 for a in agregados) or 1

                for a in agregados:
                    total_norm = (a['total'] or 0) / max_total
                    cant_norm = (a['cantidad'] or 0) / max_cant
                    score = round(0.7 * total_norm + 0.3 * cant_norm, 4) * 100
                    RankingCliente.objects.update_or_create(
                        cliente_id=a['cliente_id'],
                        defaults={'score': score}
                    )

                return list(
                    RankingCliente.objects.select_related('cliente')
                    .order_by('-score')[:10]
                )

        except Exception:
            # Si falla el cálculo, continuar con un fallback mínimo
            pass

        # Fallback: crear entradas con score 0 para clientes con pedidos recientes
        clientes_ids = (
            Pedido.objects.order_by('-fecha_pedido')
            .values_list('cliente_id', flat=True)
            .distinct()[:10]
        )
        for cid in clientes_ids:
            RankingCliente.objects.update_or_create(
                cliente_id=cid,
                defaults={'score': 0}
            )
        return RankingCliente.objects.filter(cliente_id__in=clientes_ids).select_related('cliente').order_by('-score')


class ScoreProveedorViewSet(viewsets.ModelViewSet):
    queryset = ScoreProveedor.objects.all()
    serializer_class = ScoreProveedorSerializer

    def get_queryset(self):
        qs = ScoreProveedor.objects.select_related('proveedor').all()
        if not qs.exists():
            # Fallback: calcular y persistir scores para proveedores activos
            from proveedores.models import Proveedor
            for proveedor in Proveedor.objects.filter(activo=True):
                # Usa servicio inteligente para cálculo real
                score = ProveedorInteligenteService.calcular_score(proveedor, insumo=None)
                ScoreProveedor.objects.update_or_create(
                    proveedor=proveedor,
                    defaults={'score': score}
                )
            qs = ScoreProveedor.objects.select_related('proveedor').all()
        return qs


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
