import logging

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model
from urllib.parse import parse_qs

logger = logging.getLogger(__name__)
User = get_user_model()
        
@database_sync_to_async
def get_user_from_token(token_str):
    try:
        token = AccessToken(token_str)
        user = User.objects.get(id=token['user_id'])
        logger.info("WS auth OK for user %s (id=%s)", user.email, user.id)
        return user
    except Exception as e:
        logger.warning("WS auth failed: %s", e)
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = parse_qs(scope.get('query_string', b'').decode())
        token_list = query_string.get('token', [])
        token = token_list[0] if token_list else None
        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            logger.warning("WS connection without token, query_string=%s", scope.get('query_string', b''))
            scope['user'] = AnonymousUser()
        return await super().__call__(scope, receive, send)
