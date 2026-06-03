from rest_framework import serializers
from .models import (
    Category, Product, ProductMedia,
    ProductAttribute, ProductVariant, VariantAttributeValue, ProductType
)

class CategoryTreeSerializer(serializers.ModelSerializer):
    """
    Nested Category Serializer (Shows full tree)
    """
    children = serializers.SerializerMethodField()
    full_path = serializers.CharField(read_only=True)
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'parent', 'level', 'full_path', 'is_active', 'children', 'created_at']
        read_only_fields = ['id', 'level', 'created_at']
    
    def get_children(self, obj):
        """Get child categories"""
        children = obj.children.all()
        if children:
            return CategoryTreeSerializer(children, many=True).data
        return []


class CategorySerializer(serializers.ModelSerializer):
    """Simple Category Serializer"""
    full_path = serializers.CharField(read_only=True)
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'parent', 'level', 'full_path', 'is_active', 'product_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'level', 'created_at', 'updated_at']
    
    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()
    
    def _validate_uniqueness(self, data, store, parent):
        """Check duplicate name within same parent, slug must be unique store-wide."""
        qs = Category.objects.filter(store=store)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        # Name must be unique within the same parent level
        name = data.get('name', '')
        if name:
            name_qs = qs.filter(parent=parent, name__iexact=name)
            if name_qs.exists():
                raise serializers.ValidationError({'name': 'A category with this name already exists under the same parent.'})

        # Slug must be unique store-wide (for URL routing)
        slug = data.get('slug', '')
        if slug and qs.filter(slug=slug).exists():
            raise serializers.ValidationError({'slug': 'A category with this slug already exists.'})

    def validate(self, data):
        """Validate category level, tenant isolation, and uniqueness"""
        request = self.context.get('request')
        parent = data.get('parent')
        tenant = getattr(request, 'tenant', None) if request else None

        if parent:
            if parent.level >= 2:
                raise serializers.ValidationError({'parent': 'Maximum 3 levels of categories allowed'})
            if tenant and parent.store_id != tenant.id:
                raise serializers.ValidationError({'parent': 'Parent category does not belong to your store.'})

        if tenant:
            self._validate_uniqueness(data, tenant, parent)

        return data


class ProductMediaSerializer(serializers.ModelSerializer):
    """Product Media Serializer"""
    file_url = serializers.SerializerMethodField()
    attribute_value_id = serializers.IntegerField(source='attribute_value.id', read_only=True, default=None)
    attribute_value_name = serializers.CharField(source='attribute_value.value', read_only=True, default=None)
    attribute_name = serializers.CharField(source='attribute_value.attribute.name', read_only=True, default=None)

    class Meta:
        model = ProductMedia
        fields = [
            'id', 'media_type', 'file', 'file_url', 'alt_text', 'order',
            'is_thumbnail',
            'attribute_value_id', 'attribute_value_name', 'attribute_name',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_file_url(self, obj):
        # Return a relative path (e.g. /media/products/2026/03/image.jpg).
        # The Next.js rewrite rule proxies /media/** → backend:8000/media/**,
        # so this works correctly in both Docker and local development.
        if obj.file and hasattr(obj.file, 'url'):
            return obj.file.url
        return None


class VariantAttributeValueSerializer(serializers.ModelSerializer):
    """Variant Attribute Value Serializer"""
    attribute_name = serializers.CharField(source='attribute_value.attribute.name', read_only=True)
    value = serializers.CharField(source='attribute_value.value', read_only=True)
    
    class Meta:
        model = VariantAttributeValue
        fields = ['id', 'attribute_name', 'value']
        read_only_fields = ['id']


class ProductVariantSerializer(serializers.ModelSerializer):
    """Product Variant Serializer"""
    attribute_values = VariantAttributeValueSerializer(many=True, read_only=True)
    final_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    attribute_values_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = ProductVariant
        fields = [
            'id', 'sku', 'price', 'compare_at_price', 'final_price',
            'stock', 'reserved', 'is_active', 'attribute_values', 'attribute_values_display',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'reserved', 'created_at', 'updated_at']


class ProductAttributeSerializer(serializers.ModelSerializer):
    """Selected Attributes for Product"""
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    attribute_values = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductAttribute
        fields = ['id', 'attribute', 'attribute_name', 'attribute_values']
    
    def get_attribute_values(self, obj):
        """Get all values for this attribute"""
        from attributes.serializers import AttributeValueSerializer
        values = obj.attribute.values.all()
        return AttributeValueSerializer(values, many=True).data


class ProductSerializer(serializers.ModelSerializer):
    """Complete Product Serializer"""
    category_name = serializers.CharField(source='category.full_path', read_only=True)
    media = ProductMediaSerializer(many=True, read_only=True)
    selected_attributes = ProductAttributeSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    variants_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'description', 'product_type', 'price', 'compare_at_price',
            'stock', 'reserved', 'category', 'category_name', 'is_active', 'is_featured',
            'media', 'selected_attributes', 'variants', 'variants_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'reserved', 'created_at', 'updated_at']
    
    def get_variants_count(self, obj):
        if obj.product_type == ProductType.CATALOG:
            return obj.variants.count()
        return 0

class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'id','name', 'sku', 'description', 'product_type', 'price', 'compare_at_price',
            'stock', 'category', 'is_active', 'is_featured'
        ]
        read_only_fields = ['id']  
    
    def validate_sku(self, value):
        """Ensure SKU is unique within the store"""
        request = self.context.get('request')
        product_id = self.instance.id if self.instance else None
        qs = Product.objects.filter(sku=value)
        if request and hasattr(request, 'tenant'):
            qs = qs.filter(store=request.tenant)
        if qs.exclude(id=product_id).exists():
            raise serializers.ValidationError('Product with this SKU already exists.')
        return value
    
    def validate_price(self, value):
        """Ensure price is positive"""
        if value < 0:
            raise serializers.ValidationError('Price must be a positive number.')
        return value

    def validate(self, data):
        """Prevent cross-tenant category and activating with inactive category"""
        request = self.context.get('request')
        category = data.get('category', getattr(self.instance, 'category', None))

        # Tenant isolation: category must belong to the same store
        if category and request and hasattr(request, 'tenant'):
            if category.store_id != request.tenant.id:
                raise serializers.ValidationError({
                    'category': 'Category does not belong to your store.'
                })

        # When activating, check if category is active
        is_active = data.get('is_active')
        if is_active and category and not category.is_active:
            raise serializers.ValidationError({
                'is_active': f'Cannot activate product. Category "{category.name}" is inactive. Please activate the category first.'
            })
        return data

    def update(self, instance, validated_data):
        old_sku = instance.sku
        product = super().update(instance, validated_data)
        new_sku = product.sku

        # If SKU changed, update all variant SKUs accordingly
        if old_sku != new_sku:
            for variant in product.variants.all():
                if variant.sku.startswith(old_sku):
                    variant.sku = new_sku + variant.sku[len(old_sku):]
                    variant.save(update_fields=['sku'])

        return product

class CombinationSerializer(serializers.Serializer):
    """A single attribute-value combination with optional per-variant price and stock."""
    attribute_values = serializers.ListField(
        child=serializers.UUIDField(),
        help_text='List of AttributeValue IDs (UUIDs) for this variant'
    )
    price = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        required=False, allow_null=True,
        help_text='Override price for this variant (optional)'
    )
    stock = serializers.IntegerField(
        default=0, required=False,
        help_text='Stock quantity for this variant'
    )


class GenerateCatalogRequestSerializer(serializers.Serializer):
    """
    Request to Generate Catalog Variants

    single_catalog_mode:
    - true: Generate ONE variant (radio button selection)
    - false: Generate ALL combinations (checkbox selection)

    selected_combinations: Array of selected attribute value combinations
    """
    single_catalog_mode = serializers.BooleanField(
        default=False,
        help_text='True = Single variant (radio), False = Multiple variants (checkbox)'
    )
    selected_combinations = serializers.ListField(
        child=CombinationSerializer(),
        required=False,
        default=[],
        help_text='Array of selected attribute value combinations. Empty = auto-generate all.'
    )


class StorefrontProductSerializer(serializers.ModelSerializer):
    """
    Storefront-friendly product serializer that groups variants by color
    and returns per-color images + available sizes.

    Response shape for catalog products:
    {
        ...product fields...,
        "general_images": [...],       # images with no attribute_value
        "attribute_groups": [          # one per visual attribute (e.g. Color)
            {
                "attribute_name": "Color",
                "attribute_id": 5,
                "values": [
                    {
                        "value_id": 10,
                        "value": "Red",
                        "images": [...],
                        "available_sizes": [
                            { "value_id": 20, "value": "36", "variant_id": 1, "stock": 5, "price": "29.99" },
                            ...
                        ]
                    },
                    ...
                ]
            }
        ]
    }
    """
    category_name = serializers.CharField(source='category.full_path', read_only=True)
    general_images = serializers.SerializerMethodField()
    attribute_groups = serializers.SerializerMethodField()
    all_media = serializers.SerializerMethodField()
    variants = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'sku', 'description', 'product_type', 'price', 'compare_at_price',
            'stock', 'category', 'category_name', 'is_active', 'is_featured',
            'general_images', 'attribute_groups', 'all_media', 'variants',
            'created_at', 'updated_at'
        ]

    def get_all_media(self, obj):
        return ProductMediaSerializer(
            obj.media.select_related('attribute_value__attribute').all(),
            many=True,
            context=self.context
        ).data

    def get_variants(self, obj):
        """Simple variant list for cart stock validation."""
        if obj.product_type != 'catalog':
            return []
        return [
            {'id': v.id, 'sku': v.sku, 'stock': v.stock, 'price': str(v.final_price)}
            for v in obj.variants.filter(is_active=True)
        ]

    def get_general_images(self, obj):
        """Images not linked to any attribute value — the main product images."""
        general = obj.media.filter(attribute_value__isnull=True)
        return ProductMediaSerializer(general, many=True, context=self.context).data

    def get_attribute_groups(self, obj):
        """
        Build grouped data: for each selected attribute (e.g. Color),
        list each value with its images and available other-dimension values (e.g. sizes).
        """
        if obj.product_type != 'catalog':
            return []

        selected_attrs = obj.selected_attributes.select_related('attribute').all()
        if not selected_attrs:
            return []

        variants = obj.variants.filter(is_active=True).prefetch_related(
            'attribute_values__attribute_value__attribute'
        )

        groups = []
        for prod_attr in selected_attrs:
            attr = prod_attr.attribute
            values_data = self._build_attribute_values(obj, attr, selected_attrs, variants)
            groups.append({
                'attribute_name': attr.name,
                'attribute_id': attr.id,
                'values': values_data,
            })

        return groups

    def _build_attribute_values(self, obj, attr, selected_attrs, variants):
        """Build the list of value entries for a single attribute."""
        values_data = []
        for av in attr.values.all():
            matching_variants = self._find_matching_variants(av, variants)
            if not matching_variants:
                continue

            images = obj.media.filter(attribute_value=av)
            image_data = ProductMediaSerializer(images, many=True, context=self.context).data

            other_attrs_data = self._collect_other_attribute_data(
                attr, selected_attrs, matching_variants
            )

            # For single-attribute products, include variant info directly
            # since there are no "other" attributes to nest under
            variant_info = None
            if not other_attrs_data and matching_variants:
                v = matching_variants[0]
                variant_info = {
                    'variant_id': v.id,
                    'variant_sku': v.sku,
                    'stock': v.stock,
                    'price': str(v.final_price),
                    'is_active': v.is_active,
                }

            values_data.append({
                'value_id': av.id,
                'value': av.value,
                'images': image_data,
                'available_variants': other_attrs_data,
                'variant': variant_info,
            })
        return values_data

    @staticmethod
    def _find_matching_variants(attribute_value, variants):
        """Return variants that contain the given attribute value."""
        matching = []
        for variant in variants:
            vav_ids = [
                vav.attribute_value_id
                for vav in variant.attribute_values.all()
            ]
            if attribute_value.id in vav_ids:
                matching.append(variant)
        return matching

    @staticmethod
    def _collect_other_attribute_data(current_attr, selected_attrs, matching_variants):
        """Collect available values from attributes other than *current_attr*."""
        other_attrs_data = []
        for other_prod_attr in selected_attrs:
            if other_prod_attr.attribute_id == current_attr.id:
                continue
            other_values = []
            for variant in matching_variants:
                for vav in variant.attribute_values.all():
                    if vav.attribute_value.attribute_id == other_prod_attr.attribute_id:
                        other_values.append({
                            'value_id': vav.attribute_value_id,
                            'value': vav.attribute_value.value,
                            'variant_id': variant.id,
                            'variant_sku': variant.sku,
                            'stock': variant.stock,
                            'price': str(variant.final_price),
                            'is_active': variant.is_active,
                        })
            other_attrs_data.append({
                'attribute_name': other_prod_attr.attribute.name,
                'attribute_id': other_prod_attr.attribute_id,
                'available_values': other_values,
            })
        return other_attrs_data