"""Build the console's aiohttp application from its services."""

from pathlib import Path

from aiohttp import web

from signal_console.local_api import MAX_BODY_BYTES
from signal_console.server.routes import (
    add_api_routes,
    add_camera_route,
    add_devices_routes,
    add_local_routes,
    add_models_route,
    add_setup_routes,
    add_static_routes,
    add_stream_route,
)
from signal_console.server.security import add_security_headers, build_guard
from signal_console.server.services import SERVICES_KEY, Services


def build_app(services: Services, web_dir: Path) -> web.Application:
    """Wire the guard, headers and routes.

    Args:
        services: What the routes use.
        web_dir: The built frontend (web/dist); a placeholder is served if it's missing.

    Returns:
        The app, ready for an AppRunner (or aiohttp's test client).
    """
    app = web.Application(
        middlewares=[build_guard(services.auth, services.local_key)],
        client_max_size=MAX_BODY_BYTES,  # requests are small JSON; larger is a 413
    )
    app[SERVICES_KEY] = services
    app.on_response_prepare.append(add_security_headers)
    app.on_shutdown.append(_end_streams)
    add_api_routes(app)
    add_stream_route(app)
    add_devices_routes(app)
    add_camera_route(app)
    add_models_route(app)
    add_setup_routes(app)
    add_local_routes(app)
    add_static_routes(app, web_dir)  # last: its catch-all would shadow the rest
    return app


async def _end_streams(app: web.Application) -> None:
    # Open SSE streams would otherwise hold shutdown until their next keepalive.
    app[SERVICES_KEY].events.close()
