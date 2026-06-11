from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings

from django.views.static import serve
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API Endpoints
    path('api/auth/', include('apps.accounts.urls')),
    path('api/tenant/', include('apps.tenants.urls')),
    path('api/products/', include('apps.products.urls')),
    path('api/attributes/', include('apps.attributes.urls')),
    path('api/orders/', include('apps.orders.urls')),
    path('api/storefront/', include('apps.storefront.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
]

# Serve media files — works with both runserver and daphne
if settings.DEBUG:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]