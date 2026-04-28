"""
Tenant Utility Functions - Helper methods for multi-tenant operations.

These functions make it easy to write tenant-aware queries in your views.
"""


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
        QuerySet: Filtered by current tenant, or empty if no tenant
    """
    if not hasattr(request, 'tenant') or request.tenant is None:
        return model_class.objects.none()

    return model_class.objects.filter(store=request.tenant)


def verify_store_owner(request):
    """
    Verify the authenticated user owns the current tenant store.

    Returns True if ownership is confirmed, False otherwise.
    Should be called in admin viewsets before mutating data.
    """
    if not hasattr(request, 'tenant') or request.tenant is None:
        return False
    if not request.user or not request.user.is_authenticated:
        return False
    return request.tenant.owner_id == request.user.id
