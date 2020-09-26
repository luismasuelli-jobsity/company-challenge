import urllib.parse
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from channels.auth import AuthMiddlewareStack
from rest_framework.authtoken.models import Token
import logging


logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user(token_key):
    try:
        token = Token.objects.get(key=token_key)
        return token.user
    except Token.DoesNotExist:
        return AnonymousUser()


class TokenAuthMiddleware:
    """
    Based on https://gist.github.com/rluts/22e05ed8f53f97bdd02eafdf38f3d60a
      and allowing the alternative of querystring-fetching. This whole code
      is based on the response involving Django 3.0.
    """

    def __init__(self, inner):
        self.inner = inner

    def __call__(self, scope):
        return TokenAuthMiddlewareInstance(scope, self)


class TokenAuthMiddlewareInstance:
    """
    Yeah, this is black magic:
    https://github.com/django/channels/issues/1399
    """

    def __init__(self, scope, middleware):
        self.middleware = middleware
        self.scope = dict(scope)
        self.inner = self.middleware.inner

    async def __call__(self, receive, send):
        scope = self.scope
        found_token = None
        logger.info("A connection is starting...")

        headers = dict(scope['headers'])
        if b'authorization' in headers:
            # We try to extract token from an Authorization: Token <whatever> header.
            token_name, token_key = headers[b'authorization'].decode().split()
            if token_name == 'Token':
                found_token = token_key

        if not found_token:
            # We traverse the query string in this case. The query
            # string will have a token=<whatever> parameter somewhere
            # and we're getting that <whatever> token if exists.
            query_string = scope.get('query_string', '')
            if isinstance(query_string, bytes):
                query_string = query_string.decode()
            for part in query_string.strip('?').split('&'):
                if part.startswith('token='):
                    found_token = urllib.parse.unquote(part[6:])

        if found_token:
            scope['user'] = await get_user(headers)
        else:
            scope['user'] = AnonymousUser()

        return await self.inner(scope)(receive, send)


def TokenAuthMiddlewareStack(inner):
    """
    Performs user authentication via token.

    :param inner: Further stack elements.
    :return: A token-auth-based stack.
    """

    return TokenAuthMiddleware(AuthMiddlewareStack(inner))
