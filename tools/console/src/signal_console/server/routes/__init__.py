"""Public API of signal_console.server.routes: register the console's HTTP routes."""

from signal_console.server.routes.api import add_api_routes
from signal_console.server.routes.camera import add_camera_route
from signal_console.server.routes.devices import add_devices_routes
from signal_console.server.routes.local import add_local_routes
from signal_console.server.routes.models import add_models_route
from signal_console.server.routes.setup import add_setup_routes
from signal_console.server.routes.static import add_static_routes
from signal_console.server.routes.stream import add_stream_route

__all__ = [
    "add_api_routes",
    "add_camera_route",
    "add_devices_routes",
    "add_local_routes",
    "add_models_route",
    "add_setup_routes",
    "add_static_routes",
    "add_stream_route",
]
