from rest_framework import serializers
from apps.tenants.models import Store
from apps.products.models import Product
from apps.products.utils import get_product_thumbnail_url


class StorefrontStoreSerializer(serializers.ModelSerializer):
    """Public store info for storefront header/branding."""

    class Meta:
        model = Store
        fields = ['id', 'name', 'subdomain', 'description', 'currency']


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


class TenantUserSerializer(serializers.ModelSerializer):
    """Serializer for basic TenantUser information."""
    class Meta:
        from apps.storefront.models import TenantUser
        model = TenantUser
        fields = ['id', 'email', 'first_name', 'last_name', 'phone', 'is_active', 'date_joined']
        read_only_fields = ['id', 'is_active', 'date_joined']


class TenantUserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for registering a new TenantUser (Storefront Customer)."""
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        from apps.storefront.models import TenantUser
        model = TenantUser
        fields = ['email', 'password', 'password_confirm', 'first_name', 'last_name', 'phone']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        from apps.storefront.models import TenantUser
        user = TenantUser(**validated_data)
        user.set_password(validated_data['password'])
        user.save()
        return user


class TenantUserProfileSerializer(serializers.ModelSerializer):
    """Serializer for updating Storefront Customer Profile."""
    class Meta:
        from apps.storefront.models import TenantUser
        model = TenantUser
        fields = ['first_name', 'last_name', 'phone']


class CustomerAddressSerializer(serializers.ModelSerializer):
    """Serializer for Storefront Customer Addresses."""
    class Meta:
        from apps.storefront.models import CustomerAddress
        model = CustomerAddress
        fields = [
            'id', 'label', 'address_line_1', 'address_line_2',
            'city', 'state', 'postal_code', 'country', 'is_default'
        ]
        read_only_fields = ['id']


class StorefrontChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing Storefront Customer password."""
    current_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    new_password_confirm = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "New passwords do not match."})
        return attrs
