from rest_framework import filters
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Attribute, AttributeValue
from apps.products.models import ProductAttribute, VariantAttributeValue
from .serializers import (
    AttributeSerializer,
    AttributeCreateSerializer,
    AttributeValueSerializer,
    AttributeValueCreateSerializer,
    BulkAttributeValueSerializer
)
from apps.tenants.utils import get_tenant_model
from apps.tenants.permissions import IsStoreOwner

@extend_schema(tags=['Attributes'])
@extend_schema_view(
    list=extend_schema(
        summary="List all attributes",
        description="Get all attributes with their values for current tenant"
    ),
    create=extend_schema(
        summary="Create new attribute",
        description="Create a new attribute for a category (e.g., Clothes → Size)"
    ),
    retrieve=extend_schema(
        summary="Get attribute details",
        description="Get attribute with all its values"
    ),
    update=extend_schema(
        summary="Update attribute",
        description="Update attribute name"
    ),
    destroy=extend_schema(
        summary="Delete attribute",
        description="Delete attribute and all its values"
    )
)
class AttributeViewSet(viewsets.ModelViewSet):
    """
    Attribute Management API

    Workflow:
    1. Create Attribute: POST /api/attributes/
       { "category": 1, "name": "Size" }

    2. Add Values: POST /api/attributes/{id}/add_value/
       { "value": "30" }

    3. Or Bulk Add: POST /api/attributes/{id}/add_bulk_values/
       { "values": ["30", "40", "42", "46"] }
    """
    permission_classes = [IsAuthenticated, IsStoreOwner]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']
    
    def get_queryset(self):
        """Return only attributes for current tenant"""
        return get_tenant_model(self.request, Attribute).prefetch_related('values')
    
    def get_serializer_class(self):
        """Use different serializer for creation"""
        if self.action in ['create', 'update', 'partial_update']:
            return AttributeCreateSerializer
        return AttributeSerializer

    def create(self, request, *args, **kwargs):
        """Override create to return full attribute data (with values) after creation."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # Return the full representation with values
        attribute = Attribute.objects.prefetch_related('values').get(pk=serializer.instance.pk)
        return Response(
            AttributeSerializer(attribute).data,
            status=status.HTTP_201_CREATED
        )

    def perform_create(self, serializer):
        """Create attribute and its initial values in one go."""
        attribute = serializer.save(store=self.request.tenant)

        # Handle values passed alongside the create request
        raw_values = self.request.data.get('values', [])
        if isinstance(raw_values, list) and raw_values:
            seen = set()
            to_create = []
            for v in raw_values:
                v = str(v).strip()
                if v and v not in seen:
                    seen.add(v)
                    to_create.append(AttributeValue(attribute=attribute, value=v))
            if to_create:
                AttributeValue.objects.bulk_create(to_create)

    def perform_destroy(self, instance):
        usage_count = ProductAttribute.objects.filter(attribute=instance).count()
        if usage_count > 0:
            raise serializers.ValidationError(
                {'detail': f'Cannot delete this attribute because it is used by {usage_count} product(s). Remove it from those products first.'}
            )
        instance.delete()

    @extend_schema(
        summary="Add single value to attribute",
        description="Add one value at a time (e.g., add '30' to Size attribute)",
        request=AttributeValueCreateSerializer,
        responses={201: AttributeValueSerializer}
    )
    @action(detail=True, methods=['post'])
    def add_value(self, request, pk=None):
        """
        Add single value to attribute
        
        POST /api/attributes/{id}/add_value/
        Body: { "value": "30" }
        """
        attribute = self.get_object()
        serializer = AttributeValueCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            # Check if value already exists
            value = serializer.validated_data['value']
            
            if AttributeValue.objects.filter(
                attribute=attribute,
                value=value
            ).exists():
                return Response(
                    {'error': f'Value "{value}" already exists for this attribute'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create value
            attribute_value = AttributeValue.objects.create(
                attribute=attribute,
                value=value
            )
            
            return Response({
                'message': f'Value "{value}" added successfully',
                'value': AttributeValueSerializer(attribute_value).data,
                'attribute': AttributeSerializer(attribute).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Add multiple values at once",
        description="Add multiple values in one request (e.g., ['30', '40', '42', '46'])",
        request=BulkAttributeValueSerializer,
        responses={201: AttributeSerializer}
    )
    @action(detail=True, methods=['post'])
    def add_bulk_values(self, request, pk=None):
        """
        Add multiple values at once
        
        POST /api/attributes/{id}/add_bulk_values/
        Body: { "values": ["30", "40", "42", "46"] }
        """
        attribute = self.get_object()
        serializer = BulkAttributeValueSerializer(data=request.data)
        
        if serializer.is_valid():
            values = serializer.validated_data['values']
            
            # Get existing values
            existing_values = set(
                AttributeValue.objects.filter(
                    attribute=attribute
                ).values_list('value', flat=True)
            )
            
            # Filter out duplicates
            new_values = [v for v in values if v not in existing_values]
            
            if not new_values:
                return Response(
                    {'error': 'All values already exist'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create values
            attribute_values = [
                AttributeValue(attribute=attribute, value=value)
                for value in new_values
            ]
            AttributeValue.objects.bulk_create(attribute_values)
            
            # Get updated attribute
            attribute.refresh_from_db()
            
            return Response({
                'message': f'Added {len(new_values)} values successfully',
                'added_values': new_values,
                'skipped_values': [v for v in values if v in existing_values],
                'attribute': AttributeSerializer(attribute).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Delete attribute value",
        description="Remove a specific value from attribute",
        request=None,
        responses={200: AttributeSerializer}
    )
    @action(detail=True, methods=['delete'], url_path='values/(?P<value_id>[^/.]+)')
    def delete_value(self, request, pk=None, value_id=None):
        """
        Delete single value
        
        DELETE /api/attributes/{id}/values/{value_id}/
        """
        attribute = self.get_object()
        
        try:
            value = AttributeValue.objects.get(
                id=value_id,
                attribute=attribute
            )
            value_name = value.value

            # Check if this value is used by any product variant
            usage_count = VariantAttributeValue.objects.filter(attribute_value=value).count()
            if usage_count > 0:
                return Response(
                    {'detail': f'Cannot delete "{value_name}" because it is used by {usage_count} product variant(s). Remove it from those variants first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            value.delete()
            
            return Response({
                'message': f'Value "{value_name}" deleted successfully',
                'attribute': AttributeSerializer(attribute).data
            })
        except AttributeValue.DoesNotExist:
            return Response(
                {'error': 'Value not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        summary="Get attributes by category",
        description="Get all attributes for a specific category"
    )
    @action(detail=False, methods=['get'], url_path='category/(?P<category_id>[^/.]+)')
    def by_category(self, request, category_id=None):
        """
        Get attributes by category

        GET /api/attributes/category/{category_id}/

        Walks up to the root parent category, since attributes
        are defined at the root category level.
        """
        from apps.products.models import Category
        try:
            cat = Category.objects.get(id=category_id, store=request.tenant)
            # Walk up to root category
            while cat.parent_id:
                cat = Category.objects.get(id=cat.parent_id)
            root_category_id = cat.id
        except Category.DoesNotExist:
            root_category_id = category_id

        attributes = self.get_queryset().filter(category_id=root_category_id)
        serializer = self.get_serializer(attributes, many=True)

        return Response({
            'count': attributes.count(),
            'attributes': serializer.data
        })