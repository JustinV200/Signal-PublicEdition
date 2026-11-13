"""Public API of whiteboard.daemon: the `whiteboard serve` process.

It wires display (board page, scene API, kiosk), camera (capture,
calibration, change watcher) and agent (the board agent) together, adds the
camera-backed routes and the API token guard, and publishes its port and
token in .state/ for the MCP server and CLI (see whiteboard.daemon_client).
"""

from whiteboard.daemon.serve import run_daemon

__all__ = ["run_daemon"]
