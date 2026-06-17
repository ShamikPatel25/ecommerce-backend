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


from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken

class TenantJWTAuthentication(JWTAuthentication):
    """JWT authentication for Storefront Customers (TenantUser).
    
    This class overrides get_user to fetch the user from the TenantUser table
    instead of the global accounts_user table.
    """

    def get_user(self, validated_token):
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError:
            raise InvalidToken(_("Token contained no recognizable user identification"))

        try:
            from apps.storefront.models import TenantUser
            user = TenantUser.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        except TenantUser.DoesNotExist:
            raise AuthenticationFailed(_("User not found"), code="user_not_found")

        if not user.is_active:
            raise AuthenticationFailed(_("User is inactive"), code="user_inactive")

        return user


from rest_framework_simplejwt.tokens import RefreshToken

class TenantRefreshToken(RefreshToken):
    """
    A custom RefreshToken that skips saving the token to the global OutstandingToken table.
    This prevents Foreign Key constraint errors because TenantUser is not the global User model.
    """
    @classmethod
    def for_user(cls, user):
        user_id = getattr(user, api_settings.USER_ID_FIELD)
        if not isinstance(user_id, int):
            user_id = str(user_id)

        token = cls()
        token[api_settings.USER_ID_CLAIM] = user_id

        return token
