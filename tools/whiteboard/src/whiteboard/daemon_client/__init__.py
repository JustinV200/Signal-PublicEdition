"""Public API of whiteboard.daemon_client: how the MCP server and CLI reach the daemon.

Kept apart from whiteboard.daemon so clients don't import the camera,
OpenCV or the aiohttp server just to send a request. The daemon itself uses
the state-file helpers to publish its port and API token.
"""

from whiteboard.daemon_client.connection import (
    LOOPBACK_HOST,
    DaemonConnection,
    DaemonLocation,
    DaemonStartError,
    find_daemon,
)
from whiteboard.daemon_client.fit_requests import FIT_MODES, FitMode, quad_from_numbers, send_fit
from whiteboard.daemon_client.http_api import (
    TOKEN_HEADER,
    DaemonApi,
    DaemonApiError,
    DaemonAuthError,
    DaemonUnreachableError,
)
from whiteboard.daemon_client.mjpeg import iter_jpeg_parts
from whiteboard.daemon_client.state_files import (
    LOG_FILE,
    DaemonInfo,
    create_token,
    read_daemon_info,
    read_token,
    remove_daemon_info,
    write_daemon_info,
)

__all__ = [
    "FIT_MODES",
    "LOG_FILE",
    "LOOPBACK_HOST",
    "TOKEN_HEADER",
    "DaemonApi",
    "FitMode",
    "DaemonApiError",
    "DaemonAuthError",
    "DaemonConnection",
    "DaemonInfo",
    "DaemonLocation",
    "DaemonStartError",
    "DaemonUnreachableError",
    "create_token",
    "find_daemon",
    "iter_jpeg_parts",
    "quad_from_numbers",
    "read_daemon_info",
    "read_token",
    "remove_daemon_info",
    "send_fit",
    "write_daemon_info",
]
