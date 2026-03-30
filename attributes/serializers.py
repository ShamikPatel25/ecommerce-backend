from rest_framework import serializers
from .models import Attribute, AttributeValue

class AttributeValueSerializer(serializers.ModelSerializer):
    """
    Serializer for Attribute Values
    
    Used to display values under an attribute
    """
    class Meta:
        model = AttributeValue
        fields = ['id', 'value', 'created_at']
        read_only_fields = ['id', 'created_at']


class AttributeSerializer(serializers.ModelSerializer):
    """
    Serializer for Attributes
    
    Shows attribute with all its values
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    values = AttributeValueSerializer(many=True, read_only=True)
    values_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Attribute
        fields = [
            'id',
            'category',
            'category_name',
            'name',
            'values',
            'values_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_values_count(self, obj):
        """Return count of values for this attribute"""
        return obj.values.count()
    
    def validate(self, data):
        """Ensure category belongs to same store"""
        request = self.context.get('request')
        category = data.get('category')
        
        if category and category.store != request.tenant:
            raise serializers.ValidationError({
                'category': 'Category does not belong to your store'
            })
        
        return data


class AttributeCreateSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for creating attributes.
    Values are handled by the view, not by this serializer.
    """
    class Meta:
        model = Attribute
        fields = ['id', 'category', 'name']
        read_only_fields = ['id']


class AttributeValueCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for adding single value to an attribute
    
    USAGE:
    POST /api/attributes/{attribute_id}/add_value/
    Body: { "value": "30" }
    """
    class Meta:
        model = AttributeValue
        fields = ['value']
    
    def validate_value(self, value):
        """Ensure value is not empty"""
        if not value.strip():
            raise serializers.ValidationError('Value cannot be empty')
        return value.strip()


class BulkAttributeValueSerializer(serializers.Serializer):
    """
    Serializer for adding multiple values at once
    
    USAGE:
    POST /api/attributes/{attribute_id}/add_bulk_values/
    Body: { "values": ["30", "40", "42", "46"] }
    """
    values = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1,
        help_text='List of values to add'
    )
    
    def validate_values(self, values):
        """Remove empty values and duplicates"""
        # Remove empty strings
        values = [v.strip() for v in values if v.strip()]
        
        if not values:
            raise serializers.ValidationError('At least one value is required')
        
        # Remove duplicates
        values = list(set(values))
        
        return values