"""
Tenant Utility Functions - Helper methods for multi-tenant operations.

These functions make it easy to write tenant-aware queries in your views.
"""


def get_tenant_model(request, model_class):
    """
    Get QuerySet for current tenant.
    
    With django-tenants, objects.all() is automatically scoped to the current schema.

    Usage in views:
        products = get_tenant_model(request, Product)
        # Automatically returns: Product.objects.all()

    Args:
        request: HttpRequest with tenant attached
        model_class: Django model class

    Returns:
        QuerySet: All objects in the current tenant schema
    """
    if not hasattr(request, 'tenant') or request.tenant is None:
        return model_class.objects.none()

    return model_class.objects.all()
