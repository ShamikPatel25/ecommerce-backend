from rest_framework import serializers
from .models import Store
from config.constants import RESERVED_SUBDOMAINS

class StoreSerializer(serializers.ModelSerializer):
    """
    Store Serializer - Full store details
    """
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    full_domain = serializers.CharField(source='get_full_domain', read_only=True)
    
    class Meta:
        model = Store
        fields = ['id', 'name', 'subdomain', 'description', 'logo', 
                  'currency', 'is_active', 'owner', 'owner_email',
                  'full_domain', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'owner']
    
    def validate_subdomain(self, value):
        """Ensure subdomain is lowercase and unique"""
        value = value.lower()
        
        # Check if subdomain is reserved
        if value in RESERVED_SUBDOMAINS:
            raise serializers.ValidationError(
                f'Subdomain "{value}" is reserved. Please choose another.'
            )
        
        return value


class StoreCreateSerializer(serializers.ModelSerializer):
    """
    Store Creation Serializer - Used when creating new stores
    """
    class Meta:
        model = Store
        fields = ['name', 'subdomain', 'description', 'currency']
    
    def create(self, validated_data):
        """Automatically set owner to current user"""
        request = self.context.get('request')
        validated_data['owner'] = request.user
        return super().create(validated_data)