from rest_framework import serializers
from .models import (
    Category, Product, ProductMedia, 
    ProductAttribute, ProductVariant, VariantAttributeValue
)
from attributes.models import Attribute, AttributeValue

class CategoryTreeSerializer(serializers.ModelSerializer):
    """
    Nested Category Serializer (Shows full tree)
    """
    children = serializers.SerializerMethodField()
    full_path = serializers.CharField(read_only=True)
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'parent', 'level', 'full_path', 'children', 'created_at']
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
        fields = ['id', 'name', 'slug', 'parent', 'level', 'full_path', 'product_count', 'created_at']
        read_only_fields = ['id', 'level', 'created_at']
    
    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()
    
    def validate(self, data):
        """Validate category level doesn't exceed 3"""
        parent = data.get('parent')
        if parent and parent.level >= 2:
            raise serializers.ValidationError({
                'parent': 'Maximum 3 levels of categories allowed'
            })
        return data


class ProductMediaSerializer(serializers.ModelSerializer):
    """Product Media Serializer"""
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductMedia
        fields = ['id', 'media_type', 'file', 'file_url', 'alt_text', 'order', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url'):
            return request.build_absolute_uri(obj.file.url) if request else obj.file.url
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
            'stock', 'is_active', 'attribute_values', 'attribute_values_display',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


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
            'id', 'name', 'sku', 'product_type', 'price', 'compare_at_price',
            'stock', 'category', 'category_name', 'is_active', 'is_featured',
            'media', 'selected_attributes', 'variants', 'variants_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_variants_count(self, obj):
        if obj.product_type == 'catalog':
            return obj.variants.count()
        return 0


# class ProductCreateSerializer(serializers.ModelSerializer):
#     """Simplified Product Creation"""
    
#     class Meta:
#         model = Product
#         fields = ['name', 'sku', 'product_type', 'price', 'compare_at_price', 'stock', 'category', 'is_active', 'is_featured']
class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'name', 'sku', 'product_type', 'price', 'compare_at_price',
            'stock', 'category', 'is_active', 'is_featured'
        ]
    
    def validate_sku(self, value):
        """Ensure SKU is unique"""
        product_id = self.instance.id if self.instance else None
        if Product.objects.filter(sku=value).exclude(id=product_id).exists():
            raise serializers.ValidationError('Product with this SKU already exists.')
        return value
    
    def validate_price(self, value):
        """Ensure price is positive"""
        if value < 0:
            raise serializers.ValidationError('Price must be a positive number.')
        return value

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
        child=serializers.DictField(),
        help_text='Array of selected attribute value combinations'
    )
    
    def validate_selected_combinations(self, value):
        """Validate combinations format"""
        if not value:
            raise serializers.ValidationError('At least one combination is required')
        
        for combo in value:
            if not isinstance(combo, dict):
                raise serializers.ValidationError('Each combination must be a dictionary')
            if 'attribute_values' not in combo:
                raise serializers.ValidationError('Each combination must have attribute_values')
        
        return value