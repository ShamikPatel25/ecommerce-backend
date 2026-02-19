# from django.http import JsonResponse
# from django.utils.deprecation import MiddlewareMixin
# from .models import Store

# class TenantMiddleware(MiddlewareMixin):
#     """
#     Multi-Tenant Middleware - The "Brain" of Data Isolation
    
#     HOW IT WORKS:
#     1. Extract subdomain from request URL
#     2. Query Store model to find matching tenant
#     3. Attach Store object to request (request.tenant)
#     4. All views can now access request.tenant
    
#     EXECUTION FLOW:
#     Request: GET nike.myplatform.com/api/products
#     ↓
#     Middleware extracts: subdomain = "nike"
#     ↓
#     Database query: Store.objects.get(subdomain="nike")
#     ↓
#     Attaches: request.tenant = <Store: Nike Store>
#     ↓
#     View filters: Product.objects.filter(store=request.tenant)
    
#     INTERVIEW TIP:
#     "This middleware runs on every request, making multi-tenancy 
#     transparent to views. Views don't need to manually filter by tenant."
#     """
    
#     def process_request(self, request):
#         """
#         Called before Django determines which view to execute.
        
#         Args:
#             request: HttpRequest object
            
#         Returns:
#             None: Continue to next middleware/view
#             JsonResponse: Stop execution if tenant invalid
#         """
        
#         # Get the full host (e.g., "nike.myplatform.com")
#         host = request.get_host().lower()
        
#         # Extract subdomain
#         subdomain = self.extract_subdomain(host)
        
#         # Special case: Admin panel / API docs should not require tenant
#         if self.is_exempt_path(request.path):
#             request.tenant = None
#             return None
        
#         # Handle localhost development (no subdomain)
#         if subdomain in ['localhost', '127.0.0.1', '']:
#             # For development, you can:
#             # Option A: Use a default test store
#             # Option B: Return error asking for subdomain
            
#             # Option A (Development convenience):
#             try:
#                 request.tenant = Store.objects.filter(is_active=True).first()
#                 return None
#             except Store.DoesNotExist:
#                 pass
            
#             # Option B (Strict - for production):
#             return JsonResponse({
#                 'error': 'Tenant required',
#                 'message': 'Please access via subdomain (e.g., store1.myplatform.com)'
#             }, status=400)
        
#         # Fetch tenant from database
#         try:
#             tenant = Store.objects.get(subdomain=subdomain, is_active=True)
#             request.tenant = tenant
            
#             # Optional: Add tenant to request headers for debugging
#             request.META['HTTP_X_TENANT_ID'] = str(tenant.id)
#             request.META['HTTP_X_TENANT_NAME'] = tenant.name
            
#         except Store.DoesNotExist:
#             return JsonResponse({
#                 'error': 'Store not found',
#                 'message': f'No active store found with subdomain: {subdomain}',
#                 'subdomain': subdomain
#             }, status=404)
        
#         except Store.MultipleObjectsReturned:
#             # This should never happen due to unique constraint
#             return JsonResponse({
#                 'error': 'Configuration error',
#                 'message': 'Multiple stores found with same subdomain'
#             }, status=500)
        
#         # Continue to next middleware/view
#         return None
    
#     def extract_subdomain(self, host):
#         """
#         Extract subdomain from host.
        
#         Examples:
#             nike.myplatform.com → "nike"
#             localhost:8000 → "localhost"
#             127.0.0.1:8000 → "127.0.0.1"
        
#         Args:
#             host (str): Full hostname with port
            
#         Returns:
#             str: Subdomain or hostname
#         """
#         # Remove port if present (e.g., "localhost:8000" → "localhost")
#         host = host.split(':')[0]
        
#         # Split by dots
#         parts = host.split('.')
        
#         # If localhost or IP address
#         if host in ['localhost', '127.0.0.1'] or host.replace('.', '').isdigit():
#             return host
        
#         # If full domain (e.g., nike.myplatform.com)
#         if len(parts) >= 2:
#             return parts[0]  # Return first part (subdomain)
        
#         return ''
    
#     def is_exempt_path(self, path):
#         """
#         Check if path should bypass tenant requirement.
        
#         EXEMPT PATHS:
#         - /admin/ : Django admin panel
#         - /api/auth/ : Registration/login endpoints
#         - /api/docs/ : API documentation
        
#         Args:
#             path (str): Request path
            
#         Returns:
#             bool: True if path is exempt
#         """
#         exempt_prefixes = [
#             '/admin/',
#             '/api/auth/register/',
#             '/api/auth/login/',
#             '/api/docs/',
#             '/api/schema/',
#         ]
        
#         return any(path.startswith(prefix) for prefix in exempt_prefixes)

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
            '/api/auth/register/',
            '/api/auth/login/',
            '/api/auth/token/',
            '/api/docs/',
            '/api/schema/',
            '/api/redoc/',
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
                store = Store.objects.filter(is_active=True).first()
                if not store:
                    return JsonResponse({
                        'error': 'No active store found. Please create a store first.'
                    }, status=404)
                request.tenant = store
                
                # Log with username or email
                if request.user.is_authenticated:
                    user_display = request.user.username or request.user.email
                else:
                    user_display = 'Anonymous'
                
                print(f"[TENANT: {store.subdomain}] {request.method} {request.path} (User: {user_display})")
                
            except Exception as e:
                return JsonResponse({
                    'error': f'Tenant resolution failed: {str(e)}'
                }, status=500)
        else:
            # Production mode: resolve tenant by subdomain
            try:
                store = Store.objects.get(subdomain=subdomain, is_active=True)
                request.tenant = store
                
                # Log with username or email
                if request.user.is_authenticated:
                    user_display = request.user.username or request.user.email
                else:
                    user_display = 'Anonymous'
                
                print(f"[TENANT: {store.subdomain}] {request.method} {request.path} (User: {user_display})")
                
            except Store.DoesNotExist:
                return JsonResponse({
                    'error': f'Store not found for subdomain: {subdomain}'
                }, status=404)
            except Exception as e:
                return JsonResponse({
                    'error': f'Tenant resolution failed: {str(e)}'
                }, status=500)
        
        response = self.get_response(request)
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