import logging

from django.db import DatabaseError, transaction
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from orders.models import Order
from products.models import Product, Category
from attributes.models import Attribute
from tenants.models import Store
from .models import Notification

logger = logging.getLogger(__name__)

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
        # Defer notification creation to after transaction commits,
        # so total_amount reflects the added items.
        order_id = instance.id
        store_id = instance.store_id
        customer_name = instance.customer_name
        def _create_order_notification():
            order = Order.objects.get(pk=order_id)
            notif = Notification.objects.create(
                store_id=store_id,
                notification_type=Notification.NotificationType.ORDER_CREATED,
                title='New Order',
                message=f'Order #{order_id} placed by {customer_name}',
                data={'order_id': order_id, 'total': str(order.total_amount)},
            )
            _push_to_websocket(notif)
        transaction.on_commit(_create_order_notification)
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
            transaction.on_commit(lambda n=notif: _push_to_websocket(n))


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
        transaction.on_commit(lambda n=notif: _push_to_websocket(n))
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
            transaction.on_commit(lambda n=notif: _push_to_websocket(n))


@receiver(post_delete, sender=Product)
def product_deleted_notification(sender, instance, **kwargs):
    try:
        notif = Notification.objects.create(
            store=instance.store,
            notification_type=Notification.NotificationType.PRODUCT_DELETED,
            title='Product Deleted',
            message=f'Product "{instance.name}" was deleted',
            data={'sku': instance.sku},
        )
        transaction.on_commit(lambda n=notif: _push_to_websocket(n))
    except DatabaseError:
        logger.warning('Failed to create notification for product deletion: %s', instance.pk)


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
        transaction.on_commit(lambda n=notif: _push_to_websocket(n))


@receiver(post_delete, sender=Category)
def category_deleted_notification(sender, instance, **kwargs):
    try:
        notif = Notification.objects.create(
            store=instance.store,
            notification_type=Notification.NotificationType.CATEGORY_DELETED,
            title='Category Deleted',
            message=f'Category "{instance.name}" was deleted',
            data={},
        )
        transaction.on_commit(lambda n=notif: _push_to_websocket(n))
    except DatabaseError:
        logger.warning('Failed to create notification for category deletion: %s', instance.pk)


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
        transaction.on_commit(lambda n=notif: _push_to_websocket(n))


@receiver(post_delete, sender=Attribute)
def attribute_deleted_notification(sender, instance, **kwargs):
    try:
        notif = Notification.objects.create(
            store=instance.store,
            notification_type=Notification.NotificationType.ATTRIBUTE_DELETED,
            title='Attribute Deleted',
            message=f'Attribute "{instance.name}" was deleted',
            data={'category': instance.category.name},
        )
        transaction.on_commit(lambda n=notif: _push_to_websocket(n))
    except DatabaseError:
        logger.warning('Failed to create notification for attribute deletion: %s', instance.pk)


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
        transaction.on_commit(lambda n=notif: _push_to_websocket(n))
