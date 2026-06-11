from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model  = OrderItem
    extra  = 0
    fields = ['product', 'variant', 'quantity', 'unit_price']
    readonly_fields = ['product', 'variant']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display  = ['id', 'customer_name', 'customer_email', 'status', 'total_amount', 'created_at']
    list_filter   = ['status', 'created_at']
    search_fields = ['customer_name', 'customer_email', 'customer_phone']
    readonly_fields = ['total_amount', 'created_at', 'updated_at']
    inlines       = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'product', 'quantity', 'unit_price']
