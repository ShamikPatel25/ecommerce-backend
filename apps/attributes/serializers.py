from rest_framework import serializers
from .models import Attribute, AttributeValue

class AttributeValueSerializer(serializers.ModelSerializer):

    class Meta:
        model = AttributeValue
        fields = ['id', 'value', 'created_at']
        read_only_fields = ['id', 'created_at']


class AttributeSerializer(serializers.ModelSerializer):

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
        return obj.values.count()
    
    def validate(self, data):
        request = self.context.get('request')
        category = data.get('category')
        
        return data


class AttributeCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Attribute
        fields = ['id', 'category', 'name']
        read_only_fields = ['id']

    def validate(self, data):
        request = self.context.get('request')
        category = data.get('category')
        return data


class AttributeValueCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = AttributeValue
        fields = ['value']
    
    def validate_value(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError('Value cannot be empty')
        if len(val) > 30:
            raise serializers.ValidationError('Value cannot exceed 30 characters')
        return val


class BulkAttributeValueSerializer(serializers.Serializer):

    values = serializers.ListField(
        child=serializers.CharField(max_length=30),
        min_length=1,
        help_text='List of values to add'
    )
    
    def validate_values(self, values):
        values = [v.strip() for v in values if v.strip()]
        
        if not values:
            raise serializers.ValidationError('At least one value is required')
        
        values = list(set(values))
        
        return values