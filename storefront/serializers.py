from rest_framework import serializers
from tenants.models import Store
from products.models import Product
from products.utils import get_product_thumbnail_url


class StorefrontStoreSerializer(serializers.ModelSerializer):
    """Public store info for storefront header/branding."""
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = ['id', 'name', 'subdomain', 'description', 'logo_url', 'currency']

    def get_logo_url(self, obj):
        if obj.logo and hasattr(obj.logo, 'url'):
            return obj.logo.url
        return None


class StorefrontProductListSerializer(serializers.ModelSerializer):
    """Lightweight product serializer for listing grids."""
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    thumbnail = serializers.SerializerMethodField()
    total_stock = serializers.SerializerMethodField()
    discount_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True, default=0
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'price', 'compare_at_price',
            'product_type', 'is_featured', 'category_name', 'thumbnail',
            'stock', 'total_stock', 'discount_percentage',
        ]

    def get_thumbnail(self, obj):
        return get_product_thumbnail_url(obj)

    def get_total_stock(self, obj):
        """For catalog products, sum variant stock. For single products, use product stock."""
        if obj.product_type == 'catalog':
            return sum(v.stock for v in obj.variants.filter(is_active=True))
        return obj.stock
