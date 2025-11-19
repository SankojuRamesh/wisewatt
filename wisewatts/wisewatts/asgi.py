# wisewatts/asgi.py
import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wisewatts.settings")
django.setup()

# import websocket routes from the app (change 'myapp' -> your app name)
import flowboard.routing

application = ProtocolTypeRouter({
    # HTTP requests go to Django as usual
    "http": get_asgi_application(),

    # WebSocket requests get routed to channels URLRouter
    "websocket": URLRouter(
        flowboard.routing.websocket_urlpatterns
    ),
})
