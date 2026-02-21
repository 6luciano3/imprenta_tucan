from rest_framework import routers
from .views import ComboOfertaViewSet

router = routers.DefaultRouter()
router.register(r'combos', ComboOfertaViewSet)

urlpatterns = router.urls
