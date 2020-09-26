from channels.routing import ProtocolTypeRouter, URLRouter
from application.routing.auth import TokenAuthMiddlewareStack
from chatrooms.routing import websocket_urlpatterns

channels_router = ProtocolTypeRouter({
    # (http->django views is added by default)
    'websocket': TokenAuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
