from rest_framework.permissions import BasePermission


class IsStoreOwner(BasePermission):

    message = 'You do not have permission to access this store.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        tenant = getattr(request, 'tenant', None)
        if tenant is None:
            return False
        return tenant.owner_id == request.user.id


class IsStoreOwnerRole(BasePermission):

    message = "You must be a registered store owner to perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        if getattr(request.user, 'is_superuser', False):
            return True
            
        return getattr(request.user, 'is_store_owner', False)


class IsOwnerOfStoreObject(BasePermission):

    message = "You do not own this store."

    def has_object_permission(self, request, view, obj):
        if getattr(request.user, 'is_superuser', False):
            return True
        return obj.owner == request.user
