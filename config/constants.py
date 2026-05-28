"""
Centralized constants for the ecommerce backend.
"""

# Default values
DEFAULT_COUNTRY = 'India'
DEFAULT_ADDRESS_TYPE = 'home'

# Pagination limits
NOTIFICATION_UNREAD_LIMIT = 50
NOTIFICATION_READ_LIMIT = 10
DASHBOARD_RECENT_ORDERS_LIMIT = 5
DASHBOARD_LOW_STOCK_LIMIT = 5
DASHBOARD_DAYS_RANGE = 7

# Stock threshold
LOW_STOCK_THRESHOLD = 10

# Reserved subdomains
RESERVED_SUBDOMAINS = ['www', 'api', 'admin', 'app', 'mail', 'ftp']

# Tenant middleware exempt paths
TENANT_EXEMPT_PATHS = [
    '/admin/',
    '/api/auth/',
    '/api/docs/',
    '/api/schema/',
    '/api/redoc/',
    '/api/tenant/stores/',
]

# Localhost identifiers
LOCALHOST_HOSTS = ['localhost', '127.0.0.1']
