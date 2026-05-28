import logging

from django.http import JsonResponse
from .models import Store
from config.constants import TENANT_EXEMPT_PATHS, LOCALHOST_HOSTS

logger = logging.getLogger(__name__)


class TenantMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # Skip tenant middleware for exempt paths
        if any(request.path.startswith(path) for path in TENANT_EXEMPT_PATHS):
            request.tenant = None
            return self.get_response(request)

        store = (
            self._resolve_from_tenant_header(request)
            or self._resolve_from_store_id_header(request)
        )

        # 3. Fallback: Try subdomain from Host header (production)
        if not store:
            result = self._resolve_from_host(request)
            if isinstance(result, JsonResponse):
                return result
            store = result

        request.tenant = store
        return self.get_response(request)

    def _resolve_from_tenant_header(self, request):
        """Try X-Tenant header (subdomain name from frontend middleware)."""
        tenant_subdomain = request.META.get('HTTP_X_TENANT')
        if not tenant_subdomain:
            return None
        return Store.objects.filter(
            subdomain=tenant_subdomain.lower().strip(),
            is_active=True
        ).first()

    def _resolve_from_store_id_header(self, request):
        """Try X-Store-Id header (legacy dev mode)."""
        store_id = request.META.get('HTTP_X_STORE_ID')
        if not store_id:
            return None
        try:
            return Store.objects.filter(id=store_id, is_active=True).first()
        except (ValueError, TypeError):
            logger.debug('Invalid X-Store-Id header')
            return None

    def _resolve_from_host(self, request):
        host = request.get_host()
        subdomain = self.extract_subdomain(host)
        if not subdomain or subdomain in LOCALHOST_HOSTS:
            return None
        try:
            return Store.objects.get(subdomain=subdomain, is_active=True)
        except Store.DoesNotExist:
            return JsonResponse({'error': 'Store not found'}, status=404)
        except Exception as e:
            logger.error('Tenant resolution failed: %s', e)
            return JsonResponse({'error': 'Internal server error'}, status=500)

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
        if host in LOCALHOST_HOSTS:
            return host

        # Extract subdomain
        parts = host.split('.')
        if len(parts) >= 2:
            return parts[0]

        return None
