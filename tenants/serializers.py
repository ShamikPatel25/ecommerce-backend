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
        fields = ['id', 'name', 'subdomain', 'description',
                  'currency', 'is_active', 'owner', 'owner_email',
                  'full_domain', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'owner']
    
    def validate_subdomain(self, value):
        """Ensure subdomain is lowercase, unique, and not reserved"""
        value = value.lower()

        # Check if subdomain is reserved
        if value in RESERVED_SUBDOMAINS:
            raise serializers.ValidationError(
                f'Subdomain "{value}" is reserved. Please choose another.'
            )

        # Check minimum alphanumeric characters (not counting underscores)
        alphanumeric_count = len(value.replace('_', ''))
        if alphanumeric_count < 3:
            raise serializers.ValidationError(
                'Subdomain must have at least 3 letters or numbers.'
            )

        # Check for uniqueness (exclude current instance on update)
        qs = Store.objects.filter(subdomain=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                f'Subdomain "{value}" is already taken. Please choose another.'
            )

        return value

    def validate_name(self, value):
        """Ensure store name meets requirements"""
        if len(value.strip()) < 3:
            raise serializers.ValidationError(
                'Store name must be at least 3 characters.'
            )
        return value.strip()

    def validate_description(self, value):
        """Ensure description doesn't exceed 300 characters"""
        if value and len(value) > 300:
            raise serializers.ValidationError(
                'Description cannot exceed 300 characters.'
            )
        return value


class StoreCreateSerializer(serializers.ModelSerializer):
    """
    Store Creation Serializer - Used when creating new stores
    """
    class Meta:
        model = Store
        fields = ['name', 'subdomain', 'description', 'currency']

    def validate_subdomain(self, value):
        """Ensure subdomain is lowercase, unique, and not reserved"""
        value = value.lower()

        # Check if subdomain is reserved
        if value in RESERVED_SUBDOMAINS:
            raise serializers.ValidationError(
                f'Subdomain "{value}" is reserved. Please choose another.'
            )

        # Check minimum alphanumeric characters (not counting underscores)
        alphanumeric_count = len(value.replace('_', ''))
        if alphanumeric_count < 3:
            raise serializers.ValidationError(
                'Subdomain must have at least 3 letters or numbers.'
            )

        # Check for uniqueness
        if Store.objects.filter(subdomain=value).exists():
            raise serializers.ValidationError(
                f'Subdomain "{value}" is already taken. Please choose another.'
            )

        return value

    def validate_name(self, value):
        """Ensure store name meets requirements"""
        if len(value.strip()) < 3:
            raise serializers.ValidationError(
                'Store name must be at least 3 characters.'
            )
        return value.strip()

    def validate_description(self, value):
        """Ensure description doesn't exceed 300 characters"""
        if value and len(value) > 300:
            raise serializers.ValidationError(
                'Description cannot exceed 300 characters.'
            )
        return value

    def create(self, validated_data):
        """Automatically set owner to current user"""
        request = self.context.get('request')
        validated_data['owner'] = request.user
        return super().create(validated_data)