from rest_framework.routers import SimpleRouter
from . import views

router = SimpleRouter()
router.register(r'', views.AttributeViewSet, basename='attribute')

urlpatterns = router.urls
