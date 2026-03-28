from django.db import models
from tenants.models import Store


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        ORDER_CREATED = 'order_created', 'Order Created'
        ORDER_STATUS_CHANGED = 'order_status_changed', 'Order Status Changed'
        PRODUCT_CREATED = 'product_created', 'Product Created'
        PRODUCT_UPDATED = 'product_updated', 'Product Updated'
        PRODUCT_DELETED = 'product_deleted', 'Product Deleted'
        PRODUCT_LOW_STOCK = 'product_low_stock', 'Product Low Stock'
        CATEGORY_CREATED = 'category_created', 'Category Created'
        CATEGORY_DELETED = 'category_deleted', 'Category Deleted'
        ATTRIBUTE_CREATED = 'attribute_created', 'Attribute Created'
        ATTRIBUTE_DELETED = 'attribute_deleted', 'Attribute Deleted'
        STORE_CREATED = 'store_created', 'Store Created'
        STORE_UPDATED = 'store_updated', 'Store Updated'

    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name='notifications'
    )
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
            models.Index(fields=['store', '-created_at']),
            models.Index(fields=['store', 'is_read']),
        ]

    def __str__(self):
        return f"[{self.store.subdomain}] {self.title}"
