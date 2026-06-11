from rest_framework_simplejwt.authentication import JWTAuthentication


class OptionalJWTAuthentication(JWTAuthentication):
    """JWT authentication that returns None instead of raising on invalid/expired tokens.

    Use this on views that accept both authenticated and anonymous requests
    (e.g. guest checkout) so an expired Authorization header doesn't block access.
    """

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except Exception:
            return None
