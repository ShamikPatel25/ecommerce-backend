from rest_framework.routers import SimpleRouter
from django.urls import path, include
from .views import OrderViewSet

router = SimpleRouter()
router.register(r'', OrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),
]
