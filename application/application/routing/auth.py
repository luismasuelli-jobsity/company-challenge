import urllib.parse
from channels.auth import AuthMiddlewareStack
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import AnonymousUser
from django.db import close_old_connections
import logging


logger = logging.getLogger(__name__)


class TokenAuthMiddleware:
    """
    Based on https://gist.github.com/rluts/22e05ed8f53f97bdd02eafdf38f3d60a
      and allowing the alternative of querystring-fetching.
    """

    def __init__(self, inner):
        self.inner = inner

    def __call__(self, scope):
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
            try:
                token = Token.objects.get(key=found_token)
                scope['user'] = token.user
                close_old_connections()
            except Token.DoesNotExist:
                scope['user'] = AnonymousUser()
        else:
            scope['user'] = AnonymousUser()

        return self.inner(scope)


def TokenAuthMiddlewareStack(inner):
    """
    Performs user authentication via token.

    :param inner: Further stack elements.
    :return: A token-auth-based stack.
    """

    return TokenAuthMiddleware(AuthMiddlewareStack(inner))
