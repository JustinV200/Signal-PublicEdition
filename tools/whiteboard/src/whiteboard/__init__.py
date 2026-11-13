"""whiteboard: Claude's projector + webcam whiteboard tool in the Signal monorepo.

Subpackages (each with its own README.md):
  config      settings dataclasses, TOML loader, well-known paths
  display     scene model + store, HTTP/WebSocket server, kiosk launcher, board page
  camera      capture, calibration, rectify, clean capture, change watcher
  agent       the board agent that reacts to board changes
  mcp_server  stdio MCP server, a thin client of the daemon API
  cli         the `whiteboard` command-line entry point

Run `uv run whiteboard --help` from tools/whiteboard for the command list.
"""

__version__ = "0.1.0"
