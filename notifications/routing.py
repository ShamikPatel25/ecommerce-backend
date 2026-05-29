from django.urls import re_path
from .consumers import NotificationConsumer

websocket_urlpatterns = [
    re_path(r'ws/notifications/(?P<store_id>[0-9a-f-]+)/$', NotificationConsumer.as_asgi()),
]
