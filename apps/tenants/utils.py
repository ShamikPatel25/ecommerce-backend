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
