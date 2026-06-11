from rest_framework.permissions import BasePermission


class IsStoreOwner(BasePermission):
    """
    Verify the authenticated user owns the tenant store attached to the request.

    Prevents cross-tenant access: user A cannot set X-Tenant to store B's subdomain
    and access store B's admin data.
    """
    message = 'You do not have permission to access this store.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        tenant = getattr(request, 'tenant', None)
        if tenant is None:
            return False
        return tenant.owner_id == request.user.id
