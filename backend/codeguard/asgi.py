import os
from django.core.asgi import get_asgi_application
from django.conf import settings
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeguard.settings.development')

django_asgi_app = get_asgi_application()

if settings.DEBUG:
    from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
    http_handler = ASGIStaticFilesHandler(django_asgi_app)
else:
    http_handler = django_asgi_app

from codeguard.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": http_handler,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})
