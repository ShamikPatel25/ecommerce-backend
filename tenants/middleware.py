from django.http import JsonResponse
from .models import Store


class TenantMiddleware:
    """
    Middleware to identify and attach the tenant (Store) to each request
    based on the subdomain in the request URL.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # List of paths that don't require tenant resolution
        exempt_paths = [
            '/admin/',
            '/api/auth/',
            '/api/docs/',
            '/api/schema/',
            '/api/redoc/',
            '/api/tenant/stores/',
        ]
        
        # Skip tenant middleware for exempt paths
        if any(request.path.startswith(path) for path in exempt_paths):
            request.tenant = None
            return self.get_response(request)
        
        # Extract subdomain from request
        host = request.get_host()
        subdomain = self.extract_subdomain(host)
        
        # Development mode: handle localhost
        if subdomain in ['localhost', '127.0.0.1', None]:
            try:
                # Check if frontend sent a specific store ID via header
                store = None
                store_id = request.META.get('HTTP_X_STORE_ID')
                if store_id:
                    try:
                        store = Store.objects.filter(id=int(store_id), is_active=True).first()
                    except (ValueError, TypeError):
                        store = None
                if not store:
                    # No store selected — don't fall back to random stores
                    request.tenant = None
                    return self.get_response(request)
                request.tenant = store
            except Exception as e:
                return JsonResponse({
                    'error': f'Tenant resolution failed: {str(e)}'
                }, status=500)
        else:
            # Production mode: resolve tenant by subdomain
            try:
                store = Store.objects.get(subdomain=subdomain, is_active=True)
                request.tenant = store
            except Store.DoesNotExist:
                return JsonResponse({
                    'error': f'Store not found for subdomain: {subdomain}'
                }, status=404)
            except Exception as e:
                return JsonResponse({
                    'error': f'Tenant resolution failed: {str(e)}'
                }, status=500)

        # Process the request (DRF JWT authentication happens inside the view)
        response = self.get_response(request)

        # Log AFTER response so request.user is properly set by DRF
        if request.user.is_authenticated:
            user_display = request.user.email or request.user.username
        else:
            user_display = 'Anonymous'

        tenant_label = request.tenant.subdomain if request.tenant else 'NO-TENANT'
        print(f"[TENANT: {tenant_label}] {request.method} {request.path} (User: {user_display})")

        return response
    
    def extract_subdomain(self, host):
        """
        Extract subdomain from host.
        Examples:
        - 'nike.myplatform.com' -> 'nike'
        - 'localhost:8000' -> 'localhost'
        - '127.0.0.1:8000' -> '127.0.0.1'
        """
        # Remove port if present
        host = host.split(':')[0]
        
        # Handle localhost and IP addresses
        if host in ['localhost', '127.0.0.1']:
            return host
        
        # Extract subdomain
        parts = host.split('.')
        if len(parts) >= 2:
            return parts[0]
        
        return None