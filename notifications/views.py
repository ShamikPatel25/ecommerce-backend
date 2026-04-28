from itertools import chain

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Notification
from .serializers import NotificationSerializer
from tenants.utils import get_tenant_model
from tenants.permissions import IsStoreOwner


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsStoreOwner]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return get_tenant_model(self.request, Notification).order_by('-created_at')

    def list(self, request, *args, **kwargs):
        """Return up to 50 unread + latest 10 read notifications."""
        qs = self.get_queryset()
        unread = list(qs.filter(is_read=False)[:50])
        read = list(qs.filter(is_read=True)[:10])
        serializer = self.get_serializer(list(chain(unread, read)), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=['patch'])
    def read_all(self, request):
        qs = self.get_queryset().filter(is_read=False)
        count = qs.update(is_read=True)
        return Response({'marked_read': count})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count})
