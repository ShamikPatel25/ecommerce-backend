from django.http import JsonResponse
from .models import Store


class TenantMiddleware:
    """
    Middleware to identify and attach the tenant (Store) to each request.

    Resolution order:
    1. X-Tenant header (subdomain name sent by frontend, e.g. "nike")
    2. X-Store-Id header (legacy store ID, e.g. "3")
    3. Subdomain from Host header (production: nike.myplatform.com)
    """

    EXEMPT_PATHS = [
        '/admin/',
        '/api/auth/',
        '/api/docs/',
        '/api/schema/',
        '/api/redoc/',
        '/api/tenant/stores/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # Skip tenant middleware for exempt paths
        if any(request.path.startswith(path) for path in self.EXEMPT_PATHS):
            request.tenant = None
            return self.get_response(request)

        store = None

        # 1. Try X-Tenant header (subdomain name from frontend middleware)
        tenant_subdomain = request.META.get('HTTP_X_TENANT')
        if tenant_subdomain:
            store = Store.objects.filter(
                subdomain=tenant_subdomain.lower().strip(),
                is_active=True
            ).first()

        # 2. Fallback: Try X-Store-Id header (legacy dev mode)
        if not store:
            store_id = request.META.get('HTTP_X_STORE_ID')
            if store_id:
                try:
                    store = Store.objects.filter(id=int(store_id), is_active=True).first()
                except (ValueError, TypeError):
                    pass

        # 3. Fallback: Try subdomain from Host header (production)
        if not store:
            host = request.get_host()
            subdomain = self.extract_subdomain(host)
            if subdomain and subdomain not in ['localhost', '127.0.0.1']:
                try:
                    store = Store.objects.get(subdomain=subdomain, is_active=True)
                except Store.DoesNotExist:
                    return JsonResponse({
                        'error': f'Store not found for subdomain: {subdomain}'
                    }, status=404)
                except Exception as e:
                    return JsonResponse({
                        'error': f'Tenant resolution failed: {str(e)}'
                    }, status=500)

        request.tenant = store
        return self.get_response(request)

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
