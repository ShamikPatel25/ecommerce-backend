import logging
from django.conf import settings
from django.db import connection
from django.http import Http404, JsonResponse
from django.core.exceptions import ValidationError
from django_tenants.utils import get_tenant_model, get_public_schema_name
from config.constants import TENANT_EXEMPT_PATHS, LOCALHOST_HOSTS

logger = logging.getLogger(__name__)

class TenantHeaderMiddleware:
    """
    Middleware that determines the tenant (schema) based on the X-Store-Id or X-Tenant header.
    Replaces django-tenants's default TenantMainMiddleware to allow SPA header routing.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        TenantModel = get_tenant_model()
        public_schema_name = get_public_schema_name()

        # Try to get tenant from headers
        tenant_identifier = request.META.get('HTTP_X_STORE_ID') or request.META.get('HTTP_X_TENANT')
        tenant = None

        if tenant_identifier:
            try:
                # Try to look up by ID first (UUID from X-Store-Id)
                tenant = TenantModel.objects.get(id=tenant_identifier)
            except (TenantModel.DoesNotExist, ValueError, ValidationError):
                try:
                    # Fallback: try to look up by schema_name or subdomain (X-Tenant)
                    tenant = TenantModel.objects.get(schema_name=tenant_identifier.lower().strip())
                except TenantModel.DoesNotExist:
                    pass
        
        # If no tenant from headers, check if it's hitting a subdomain
        if not tenant:
            host = request.get_host().split(':')[0]
            if host not in LOCALHOST_HOSTS:
                parts = host.split('.')
                if len(parts) >= 2:
                    subdomain = parts[0]
                    try:
                        tenant = TenantModel.objects.get(subdomain=subdomain)
                    except TenantModel.DoesNotExist:
                        pass

        if not tenant:
            # If no valid tenant, default to public schema
            try:
                tenant = TenantModel.objects.get(schema_name=public_schema_name)
            except TenantModel.DoesNotExist:
                tenant = TenantModel(schema_name=public_schema_name)
        
        # Attach tenant to request and set the active database schema
        request.tenant = tenant
        connection.set_tenant(request.tenant)

        # Set URL configuration based on schema
        if tenant.schema_name == public_schema_name and hasattr(settings, 'PUBLIC_SCHEMA_URLCONF'):
            request.urlconf = settings.PUBLIC_SCHEMA_URLCONF
        elif hasattr(settings, 'ROOT_URLCONF'):
            request.urlconf = settings.ROOT_URLCONF

        response = self.get_response(request)
        return response
