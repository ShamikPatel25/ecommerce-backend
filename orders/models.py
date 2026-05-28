from django.db import models
from products.models import Product, ProductVariant
from config.constants import DEFAULT_COUNTRY, DEFAULT_ADDRESS_TYPE


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending',          'Pending'),
        ('confirmed',        'Confirmed'),
        ('processing',       'Processing'),
        ('shipped',          'Shipped'),
        ('delivered',        'Delivered'),
        ('cancelled',        'Cancelled'),
        ('returned',         'Returned'),
    ]

    # Valid status transitions
    VALID_TRANSITIONS = {
        'pending':          ['confirmed', 'cancelled'],
        'confirmed':        ['processing', 'cancelled'],
        'processing':       ['shipped', 'cancelled'],
        'shipped':          ['delivered'],
        'delivered':        ['returned'],
        'cancelled':        [],
        'returned':         [],
    }

    ADDRESS_TYPE_CHOICES = [
        ('home',  'Home'),
        ('work',  'Work'),
        ('other', 'Other'),
    ]

    store           = models.ForeignKey(
        'tenants.Store', on_delete=models.CASCADE, related_name='orders'
    )
    customer_name   = models.CharField(max_length=255)
    customer_email  = models.EmailField()
    customer_phone  = models.CharField(max_length=30)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_amount    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes           = models.TextField(blank=True, default='')

    # Shipping address
    address_line_1  = models.CharField(max_length=255, blank=True, default='')
    address_line_2  = models.CharField(max_length=255, blank=True, default='')
    city            = models.CharField(max_length=100, blank=True, default='')
    state           = models.CharField(max_length=100, blank=True, default='')
    postal_code     = models.CharField(max_length=20, blank=True, default='')
    country         = models.CharField(max_length=100, blank=True, default=DEFAULT_COUNTRY)
    address_type    = models.CharField(max_length=10, choices=ADDRESS_TYPE_CHOICES, default=DEFAULT_ADDRESS_TYPE)

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['store', 'status']),
            models.Index(fields=['store', 'customer_email']),
            models.Index(fields=['store', 'created_at']),
        ]

    def __str__(self):
        return f"Order #{self.id} — {self.customer_name} ({self.status})"

    @property
    def shipping_address(self):
        parts = [self.address_line_1]
        if self.address_line_2:
            parts.append(self.address_line_2)
        if self.city or self.state or self.postal_code:
            city_state = ', '.join(filter(None, [self.city, self.state, self.postal_code]))
            parts.append(city_state)
        if self.country:
            parts.append(self.country)
        return '\n'.join(parts) if self.address_line_1 else ''

    def recalculate_total(self):
        self.total_amount = sum(
            item.unit_price * item.quantity for item in self.items.all()
        )
        self.save(update_fields=['total_amount'])


class OrderItem(models.Model):
    ITEM_STATUS_CHOICES = [
        ('ordered',   'Ordered'),
        ('cancelled', 'Cancelled'),
        ('returned',  'Returned'),
    ]

    order      = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product    = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name='order_items')
    variant    = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items'
    )
    quantity   = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    status     = models.CharField(max_length=20, choices=ITEM_STATUS_CHOICES, default='ordered')

    # Snapshot fields - preserve product info even if product is deleted
    product_name_snapshot = models.CharField(max_length=255, blank=True, default='')
    product_sku_snapshot = models.CharField(max_length=100, blank=True, default='')
    product_slug_snapshot = models.CharField(max_length=255, blank=True, default='')
    product_thumbnail_snapshot = models.URLField(max_length=500, blank=True, default='')
    variant_attrs_snapshot = models.CharField(max_length=500, blank=True, default='')

    def __str__(self):
        name = self.product_name_snapshot or (self.product.name if self.product else 'Unknown')
        return f"{self.quantity}× {name} (Order #{self.order_id})"

    @property
    def subtotal(self):
        return self.unit_price * self.quantity
