import re
from rest_framework import serializers
from .models import Order, OrderItem
from products.models import Product, ProductVariant


class OrderItemSerializer(serializers.ModelSerializer):
    product_name  = serializers.CharField(source='product.name', read_only=True)
    product_sku   = serializers.CharField(source='product.sku', read_only=True)
    product_slug  = serializers.CharField(source='product.slug', read_only=True)
    variant_attrs = serializers.CharField(
        source='variant.attribute_values_display', read_only=True
    )
    subtotal      = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    thumbnail     = serializers.SerializerMethodField()

    class Meta:
        model  = OrderItem
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'product_slug',
            'variant', 'variant_attrs',
            'quantity', 'unit_price', 'subtotal', 'thumbnail',
        ]
        read_only_fields = ['id']

    def get_thumbnail(self, obj):
        if not obj.product:
            return None
        thumb = obj.product.media.filter(media_type='image', is_thumbnail=True).first()
        if not thumb:
            thumb = obj.product.media.filter(media_type='image').first()
        if thumb and thumb.file and hasattr(thumb.file, 'url'):
            return thumb.file.url
        return None


class OrderSerializer(serializers.ModelSerializer):
    items         = OrderItemSerializer(many=True, read_only=True)
    items_count   = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model  = Order
        fields = [
            'id', 'customer_name', 'customer_email', 'customer_phone',
            'status', 'status_display', 'total_amount', 'notes',
            'items', 'items_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'total_amount', 'created_at', 'updated_at']

    def get_items_count(self, obj):
        return obj.items.count()


class OrderItemCreateSerializer(serializers.Serializer):
    product  = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    variant  = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(), required=False, allow_null=True, default=None
    )
    quantity   = serializers.IntegerField(min_value=1, default=1)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)


class OrderCreateSerializer(serializers.Serializer):
    customer_name  = serializers.CharField(max_length=255)
    customer_email = serializers.EmailField()
    customer_phone = serializers.CharField(max_length=10, min_length=10)
    notes          = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    items          = OrderItemCreateSerializer(many=True)

    def validate_customer_phone(self, value):
        if not re.match(r'^\d{10}$', value):
            raise serializers.ValidationError('Phone must be exactly 10 digits.')
        return value

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('Order must have at least one item.')
        return value


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES)
    notes  = serializers.CharField(required=False, allow_blank=True, allow_null=True)
