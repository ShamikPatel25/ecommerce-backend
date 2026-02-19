from django.urls import path, include
from rest_framework.routers import SimpleRouter
from . import views

router = SimpleRouter()
router.register(r'stores', views.StoreViewSet, basename='store')

urlpatterns = [
    path('', include(router.urls)),
    path('info/', views.tenant_info, name='tenant-info'),
]