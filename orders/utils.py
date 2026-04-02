from django.db.models import F, Value
from django.db.models.functions import Greatest
from products.models import Product, ProductVariant


def decrement_stock(item_data):
    """Order placed — stock -1, reserved +1."""
    product = item_data['product']
    variant = item_data.get('variant')
    qty = item_data['quantity']

    if variant:
        v = ProductVariant.objects.select_for_update().get(pk=variant.pk)
        if v.stock < qty:
            raise ValueError(
                f'Insufficient stock for variant "{v.sku}": '
                f'requested {qty}, available {v.stock}'
            )
        v.stock = F('stock') - qty
        v.reserved = F('reserved') + qty
        v.save(update_fields=['stock', 'reserved'])
    else:
        p = Product.objects.select_for_update().get(pk=product.pk if hasattr(product, 'pk') else product)
        if p.stock < qty:
            raise ValueError(
                f'Insufficient stock for "{p.name}": '
                f'requested {qty}, available {p.stock}'
            )
        p.stock = F('stock') - qty
        p.reserved = F('reserved') + qty
        p.save(update_fields=['stock', 'reserved'])


def restore_stock(order):
    """Order cancelled (before shipping) — stock +1, reserved -1."""
    for item in order.items.select_related('product', 'variant').all():
        if item.variant:
            ProductVariant.objects.filter(pk=item.variant_id).update(
                stock=F('stock') + item.quantity,
                reserved=Greatest(F('reserved') - item.quantity, Value(0)),
            )
        elif item.product:
            Product.objects.filter(pk=item.product_id).update(
                stock=F('stock') + item.quantity,
                reserved=Greatest(F('reserved') - item.quantity, Value(0)),
            )


def reduce_reserved(order):
    """Order shipped — reserved -1 (bottle left shelf)."""
    for item in order.items.select_related('product', 'variant').all():
        if item.variant:
            ProductVariant.objects.filter(pk=item.variant_id).update(
                reserved=Greatest(F('reserved') - item.quantity, Value(0)),
            )
        elif item.product:
            Product.objects.filter(pk=item.product_id).update(
                reserved=Greatest(F('reserved') - item.quantity, Value(0)),
            )


def restore_stock_only(order):
    """Order returned (bottle back at store) — stock +1, reserved already 0."""
    for item in order.items.select_related('product', 'variant').all():
        if item.variant:
            ProductVariant.objects.filter(pk=item.variant_id).update(
                stock=F('stock') + item.quantity,
            )
        elif item.product:
            Product.objects.filter(pk=item.product_id).update(
                stock=F('stock') + item.quantity,
            )
