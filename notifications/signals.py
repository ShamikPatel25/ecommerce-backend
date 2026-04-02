from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from orders.models import Order
from products.models import Product, Category
from attributes.models import Attribute
from tenants.models import Store
from .models import Notification

LOW_STOCK_THRESHOLD = 5


def _push_to_websocket(notification):
    """Send notification to the store's WebSocket group."""
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    group_name = f'store_{notification.store_id}_notifications'
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'send_notification',
            'data': {
                'id': notification.id,
                'notification_type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'data': notification.data,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat(),
            },
        },
    )


# ──────────────────────── ORDER ────────────────────────

@receiver(pre_save, sender=Order)
def cache_old_order_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old_status = Order.objects.get(pk=instance.pk).status
        except Order.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Order)
def order_notification(sender, instance, created, **kwargs):
    if created:
        notif = Notification.objects.create(
            store=instance.store,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title='New Order',
            message=f'Order #{instance.id} placed by {instance.customer_name}',
            data={'order_id': instance.id, 'total': str(instance.total_amount)},
        )
        _push_to_websocket(notif)
    else:
        old_status = getattr(instance, '_old_status', None)
        if old_status and old_status != instance.status:
            notif = Notification.objects.create(
                store=instance.store,
                notification_type=Notification.NotificationType.ORDER_STATUS_CHANGED,
                title='Order Status Updated',
                message=f'Order #{instance.id}: {old_status} → {instance.status}',
                data={'order_id': instance.id, 'old_status': old_status, 'new_status': instance.status},
            )
            _push_to_websocket(notif)


# ──────────────────────── PRODUCT ────────────────────────

@receiver(post_save, sender=Product)
def product_notification(sender, instance, created, **kwargs):
    if created:
        notif = Notification.objects.create(
            store=instance.store,
            notification_type=Notification.NotificationType.PRODUCT_CREATED,
            title='Product Created',
            message=f'New product "{instance.name}" added',
            data={'product_id': instance.id, 'sku': instance.sku},
        )
        _push_to_websocket(notif)
    else:
        # Guard: after F() expression updates, instance.stock may be a
        # CombinedExpression instead of an int. Refresh from DB first.
        stock = instance.stock
        if not isinstance(stock, (int, float)):
            instance.refresh_from_db(fields=['stock'])
            stock = instance.stock
        if instance.product_type == 'single' and stock <= LOW_STOCK_THRESHOLD:
            notif = Notification.objects.create(
                store=instance.store,
                notification_type=Notification.NotificationType.PRODUCT_LOW_STOCK,
                title='Low Stock Alert',
                message=f'"{instance.name}" has only {stock} units left',
                data={'product_id': instance.id, 'stock': stock},
            )
            _push_to_websocket(notif)


@receiver(post_delete, sender=Product)
def product_deleted_notification(sender, instance, **kwargs):
    notif = Notification.objects.create(
        store=instance.store,
        notification_type=Notification.NotificationType.PRODUCT_DELETED,
        title='Product Deleted',
        message=f'Product "{instance.name}" was deleted',
        data={'sku': instance.sku},
    )
    _push_to_websocket(notif)


# ──────────────────────── CATEGORY ────────────────────────

@receiver(post_save, sender=Category)
def category_notification(sender, instance, created, **kwargs):
    if created:
        notif = Notification.objects.create(
            store=instance.store,
            notification_type=Notification.NotificationType.CATEGORY_CREATED,
            title='Category Created',
            message=f'New category "{instance.name}" added',
            data={'category_id': instance.id},
        )
        _push_to_websocket(notif)


@receiver(post_delete, sender=Category)
def category_deleted_notification(sender, instance, **kwargs):
    notif = Notification.objects.create(
        store=instance.store,
        notification_type=Notification.NotificationType.CATEGORY_DELETED,
        title='Category Deleted',
        message=f'Category "{instance.name}" was deleted',
        data={},
    )
    _push_to_websocket(notif)


# ──────────────────────── ATTRIBUTE ────────────────────────

@receiver(post_save, sender=Attribute)
def attribute_notification(sender, instance, created, **kwargs):
    if created:
        notif = Notification.objects.create(
            store=instance.store,
            notification_type=Notification.NotificationType.ATTRIBUTE_CREATED,
            title='Attribute Created',
            message=f'New attribute "{instance.name}" added to {instance.category.name}',
            data={'attribute_id': instance.id, 'category': instance.category.name},
        )
        _push_to_websocket(notif)


@receiver(post_delete, sender=Attribute)
def attribute_deleted_notification(sender, instance, **kwargs):
    notif = Notification.objects.create(
        store=instance.store,
        notification_type=Notification.NotificationType.ATTRIBUTE_DELETED,
        title='Attribute Deleted',
        message=f'Attribute "{instance.name}" was deleted',
        data={'category': instance.category.name},
    )
    _push_to_websocket(notif)


# ──────────────────────── STORE ────────────────────────

@receiver(post_save, sender=Store)
def store_notification(sender, instance, created, **kwargs):
    if created:
        notif = Notification.objects.create(
            store=instance,
            notification_type=Notification.NotificationType.STORE_CREATED,
            title='Store Created',
            message=f'Store "{instance.name}" is now live',
            data={'store_id': instance.id, 'subdomain': instance.subdomain},
        )
        _push_to_websocket(notif)
