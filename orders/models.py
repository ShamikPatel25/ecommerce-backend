from django.db import models
from products.models import Product, ProductVariant


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending',          'Pending'),
        ('confirmed',        'Confirmed'),
        ('processing',       'Processing'),
        ('shipped',          'Shipped'),
        ('delivered',        'Delivered'),
        ('cancelled',        'Cancelled'),
        ('return_requested', 'Return Requested'),
        ('returned',         'Returned'),
    ]

    # Valid status transitions
    VALID_TRANSITIONS = {
        'pending':          ['confirmed', 'cancelled'],
        'confirmed':        ['processing', 'cancelled'],
        'processing':       ['shipped', 'cancelled'],
        'shipped':          ['delivered'],
        'delivered':        ['return_requested'],
        'return_requested': ['returned'],
        'cancelled':        [],
        'returned':         [],
    }

    store           = models.ForeignKey(
        'tenants.Store', on_delete=models.CASCADE, related_name='orders'
    )
    customer_name   = models.CharField(max_length=255)
    customer_email  = models.EmailField()
    customer_phone  = models.CharField(max_length=30)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_amount    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes           = models.TextField(blank=True, null=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} — {self.customer_name} ({self.status})"

    def recalculate_total(self):
        self.total_amount = sum(
            item.unit_price * item.quantity for item in self.items.all()
        )
        self.save(update_fields=['total_amount'])


class OrderItem(models.Model):
    order      = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product    = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name='order_items')
    variant    = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items'
    )
    quantity   = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}× {self.product} (Order #{self.order_id})"

    @property
    def subtotal(self):
        return self.unit_price * self.quantity
