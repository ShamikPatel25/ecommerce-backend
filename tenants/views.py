from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import Store
from .serializers import StoreSerializer, StoreCreateSerializer

@extend_schema(tags=['Stores'])
@extend_schema_view(
    list=extend_schema(
        summary="List user's stores",
        description="Get all stores owned by the authenticated user"
    ),
    create=extend_schema(
        summary="Create new store",
        description="Create a new store/tenant. Subdomain must be unique."
    ),
    retrieve=extend_schema(
        summary="Get store details",
        description="Retrieve detailed information about a specific store"
    ),
    update=extend_schema(
        summary="Update store",
        description="Update store information"
    ),
    destroy=extend_schema(
        summary="Delete store",
        description="Permanently delete a store and all associated data"
    )
)
class StoreViewSet(viewsets.ModelViewSet):
    """Multi-tenant store management"""
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return only stores owned by current user"""
        return Store.objects.filter(owner=self.request.user)
    
    def get_serializer_class(self):
        """Use different serializer for creation"""
        if self.action == 'create':
            return StoreCreateSerializer
        return StoreSerializer
    
    def create(self, request, *args, **kwargs):
        """Create new store"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = serializer.save()
        
        return Response({
            'store': StoreSerializer(store).data,
            'message': f'Store "{store.name}" created successfully'
        }, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="Get my stores",
        description="Get all stores owned by current user with count"
    )
    @action(detail=False, methods=['get'])
    def my_stores(self, request):
        """Get all stores owned by current user"""
        stores = self.get_queryset()
        serializer = self.get_serializer(stores, many=True)
        
        return Response({
            'count': stores.count(),
            'stores': serializer.data
        })
    
    @extend_schema(
        summary="Toggle store active status",
        description="Enable or disable a store"
    )
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle store active status"""
        store = self.get_object()
        store.is_active = not store.is_active
        store.save()
        
        return Response({
            'store': StoreSerializer(store).data,
            'message': f'Store is now {"active" if store.is_active else "inactive"}'
        })


@extend_schema(
    tags=['Stores'],
    summary="Get tenant info",
    description="Returns current tenant/store information based on subdomain"
)
@api_view(['GET'])
@permission_classes([AllowAny])
def tenant_info(request):
    """Get current tenant information"""
    tenant = getattr(request, 'tenant', None)
    
    if tenant is None:
        return Response({
            'error': 'No tenant found'
        }, status=400)
    
    return Response({
        'tenant_id': tenant.id,
        'tenant_name': tenant.name,
        'subdomain': tenant.subdomain,
        'currency': tenant.currency,
        'is_active': tenant.is_active,
        'message': f'✅ Successfully connected to {tenant.name}'
    })