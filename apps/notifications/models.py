import uuid
from django.db import models


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class NotificationType(models.TextChoices):
        ORDER_CREATED = 'order_created', 'Order Created'
        ORDER_STATUS_CHANGED = 'order_status_changed', 'Order Status Changed'
        PRODUCT_CREATED = 'product_created', 'Product Created'
        PRODUCT_DELETED = 'product_deleted', 'Product Deleted'
        PRODUCT_LOW_STOCK = 'product_low_stock', 'Product Low Stock'
        CATEGORY_CREATED = 'category_created', 'Category Created'
        CATEGORY_DELETED = 'category_deleted', 'Category Deleted'
        ATTRIBUTE_CREATED = 'attribute_created', 'Attribute Created'
        ATTRIBUTE_DELETED = 'attribute_deleted', 'Attribute Deleted'
        STORE_CREATED = 'store_created', 'Store Created'

    notification_type = models.CharField(
        max_length=30, choices=NotificationType.choices
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['is_read']),
        ]

    def __str__(self):
        return f"{self.title}"
