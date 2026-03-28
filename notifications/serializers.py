from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(
        source='get_notification_type_display', read_only=True
    )

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'type_display',
            'title', 'message', 'data', 'is_read', 'created_at',
        ]
        read_only_fields = fields
