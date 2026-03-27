from django.urls import path, include
from .api_inteligente import router
from automatizacion.api.api_recomendacion import RecomendacionProveedorAPIView
from automatizacion.api.api_orden_automatica import OrdenCompraAutomaticaAPIView
from automatizacion.api.api_feedback import FeedbackRecomendacionAPIView
from automatizacion.api.api_feedback import CriteriosPesosAPIView
from automatizacion.api import api_tracking

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/recomendar-proveedor/', RecomendacionProveedorAPIView.as_view(), name='api_recomendar_proveedor'),
    path('api/orden-automatica/', OrdenCompraAutomaticaAPIView.as_view(), name='api_orden_automatica'),
    path('api/feedback-recomendacion/', FeedbackRecomendacionAPIView.as_view(), name='api_feedback_recomendacion'),
    path('api/criterios-pesos/', CriteriosPesosAPIView.as_view(), name='api_criterios_pesos'),
    
    # Tracking de emails
    path('api/tracking/open/<str:token>/', api_tracking.tracking_open, name='tracking_open'),
    path('api/tracking/click/<str:token>/', api_tracking.tracking_click, name='tracking_click'),
    path('api/tracking/unsubscribe/<str:token>/', api_tracking.tracking_unsubscribe, name='tracking_unsubscribe'),
    path('api/tracking/response/', api_tracking.email_response, name='email_response'),
    path('api/tracking/stats/<str:token>/', api_tracking.tracking_stats, name='tracking_stats'),
]
