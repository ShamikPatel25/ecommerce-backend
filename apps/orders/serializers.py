import re
from rest_framework import serializers
from .models import Order, OrderItem
from apps.products.models import Product, ProductVariant
from apps.products.utils import get_product_thumbnail_url
from config.constants import DEFAULT_COUNTRY, DEFAULT_ADDRESS_TYPE


class OrderItemSerializer(serializers.ModelSerializer):
    product_name  = serializers.SerializerMethodField()
    product_sku   = serializers.SerializerMethodField()
    product_slug  = serializers.SerializerMethodField()
    variant_attrs = serializers.SerializerMethodField()
    subtotal      = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    thumbnail     = serializers.SerializerMethodField()

    class Meta:
        model  = OrderItem
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'product_slug',
            'variant', 'variant_attrs',
            'quantity', 'unit_price', 'subtotal', 'thumbnail', 'status',
        ]
        read_only_fields = ['id']

    def get_product_name(self, obj):
        if obj.product:
            return obj.product.name
        return obj.product_name_snapshot or None

    def get_product_sku(self, obj):
        if obj.product:
            return obj.product.sku
        return obj.product_sku_snapshot or None

    def get_product_slug(self, obj):
        if obj.product:
            return obj.product.slug
        return obj.product_slug_snapshot or None

    def get_variant_attrs(self, obj):
        if obj.variant and hasattr(obj.variant, 'attribute_values_display'):
            return obj.variant.attribute_values_display
        return obj.variant_attrs_snapshot or None

    def get_thumbnail(self, obj):
        if obj.product:
            return get_product_thumbnail_url(obj.product)
        return obj.product_thumbnail_snapshot or None


class OrderSerializer(serializers.ModelSerializer):
    items         = OrderItemSerializer(many=True, read_only=True)
    items_count   = serializers.SerializerMethodField()
    active_items_count = serializers.SerializerMethodField()
    active_total  = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    shipping_address = serializers.CharField(read_only=True)
    class Meta:
        model  = Order
        fields = [
            'id', 'order_number', 'customer_name', 'customer_email', 'customer_phone',
            'status', 'status_display', 'total_amount', 'active_total', 'notes',
            'address_line_1', 'address_line_2', 'city', 'state',
            'postal_code', 'country', 'address_type', 'shipping_address',
            'items', 'items_count', 'active_items_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'order_number', 'total_amount', 'created_at', 'updated_at']

    def get_items_count(self, obj):
        return obj.items.count()

    def get_active_items_count(self, obj):
        return obj.items.exclude(status__in=['cancelled', 'returned']).count()

    def get_active_total(self, obj):
        from decimal import Decimal
        active_items = obj.items.exclude(status__in=['cancelled', 'returned'])
        total = sum(item.unit_price * item.quantity for item in active_items)
        return Decimal(total).quantize(Decimal('0.01'))


class OrderItemCreateSerializer(serializers.Serializer):
    product  = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    variant  = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(), required=False, allow_null=True, default=None
    )
    quantity   = serializers.IntegerField(
        min_value=1, 
        max_value=20, 
        default=1,
        error_messages={'max_value': 'Cannot order more than 20 of the same item.'}
    )
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    def validate(self, data):
        # Ensure variant belongs to the specified product
        if data.get('variant') and data['variant'].product_id != data['product'].id:
            raise serializers.ValidationError(
                {'variant': 'This variant does not belong to the specified product.'}
            )
        return data


class OrderCreateSerializer(serializers.Serializer):
    customer_name  = serializers.CharField(max_length=255)
    customer_email = serializers.EmailField()
    customer_phone = serializers.CharField(max_length=15, min_length=10)
    notes          = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    items          = OrderItemCreateSerializer(many=True)

    # Shipping address
    address_line_1 = serializers.CharField(max_length=255)
    address_line_2 = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    city           = serializers.CharField(max_length=100)
    state          = serializers.CharField(max_length=100)
    postal_code    = serializers.CharField(max_length=20)
    country        = serializers.CharField(max_length=100, required=False, default=DEFAULT_COUNTRY)
    address_type   = serializers.ChoiceField(
        choices=Order.ADDRESS_TYPE_CHOICES, required=False, default=DEFAULT_ADDRESS_TYPE
    )

    def validate_customer_phone(self, value):
        if not re.match(r'^\d{10,15}$', value):
            raise serializers.ValidationError('Phone must be 10-15 digits.')
        return value

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('Order must have at least one item.')
        
        item_counts = {}
        for item in value:
            key = (item['product'].id, item.get('variant').id if item.get('variant') else None)
            item_counts[key] = item_counts.get(key, 0) + item.get('quantity', 1)
            if item_counts[key] > 20:
                raise serializers.ValidationError('Cannot order more than 20 of the same item.')
                
        return value


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES)
    notes  = serializers.CharField(required=False, allow_blank=True, allow_null=True)
