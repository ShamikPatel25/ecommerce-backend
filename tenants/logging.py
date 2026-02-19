import logging

logger = logging.getLogger(__name__)

class TenantLoggingMiddleware:
    """
    Middleware to log tenant information for debugging.
    
    Useful during development to track which tenant is handling each request.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            logger.info(
                f"[TENANT: {tenant.subdomain}] "
                f"{request.method} {request.path} "
                f"(User: {request.user.email if request.user.is_authenticated else 'Anonymous'})"
            )
        
        response = self.get_response(request)
        return response