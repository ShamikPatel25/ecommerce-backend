"""
Tenant Utility Functions - Helper methods for multi-tenant operations.

These functions make it easy to write tenant-aware queries in your views.
"""

from django.core.exceptions import PermissionDenied

def get_tenant_model(request, model_class):
    """
    Get QuerySet filtered by current tenant.
    
    Usage in views:
        products = get_tenant_model(request, Product)
        # Automatically returns: Product.objects.filter(store=request.tenant)
    
    Args:
        request: HttpRequest with tenant attached
        model_class: Django model class
        
    Returns:
        QuerySet: Filtered by current tenant
    """
    if not hasattr(request, 'tenant') or request.tenant is None:
        raise ValueError('Request must have tenant attached by middleware')
    
    return model_class.objects.filter(store=request.tenant)


def validate_tenant_ownership(request, obj):
    """
    Verify that object belongs to current tenant.
    
    Use Case: When updating/deleting, ensure user can't modify other tenants' data
    
    Usage:
        product = Product.objects.get(id=product_id)
        validate_tenant_ownership(request, product)  # Raises error if wrong tenant
    
    Args:
        request: HttpRequest with tenant
        obj: Model instance to check
        
    Raises:
        PermissionDenied: If object doesn't belong to current tenant
    """
    if not hasattr(obj, 'store'):
        raise ValueError(f'{obj.__class__.__name__} model must have a "store" field')
    
    if obj.store != request.tenant:
        raise PermissionDenied('You do not have permission to access this resource')


def get_current_tenant(request):
    """
    Safely get current tenant from request.
    
    Returns:
        Store: Current tenant or None
    """
    return getattr(request, 'tenant', None)