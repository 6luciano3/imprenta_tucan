from django.urls import path, include
from .api_inteligente import router
from automatizacion.api.api_recomendacion import RecomendacionProveedorAPIView
from automatizacion.api.api_orden_automatica import OrdenCompraAutomaticaAPIView
from automatizacion.api.api_feedback import FeedbackRecomendacionAPIView

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/recomendar-proveedor/', RecomendacionProveedorAPIView.as_view(), name='api_recomendar_proveedor'),
    path('api/orden-automatica/', OrdenCompraAutomaticaAPIView.as_view(), name='api_orden_automatica'),
    path('api/feedback-recomendacion/', FeedbackRecomendacionAPIView.as_view(), name='api_feedback_recomendacion'),
]
