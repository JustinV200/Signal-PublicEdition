"""Public API of browser_tool.server: the MCP server and its stdio entry point."""

from browser_tool.server.app import (
    DOCKER_INSTRUCTIONS,
    DOCKER_SERVER_NAME,
    INSTRUCTIONS,
    SERVER_NAME,
    build_server,
)
from browser_tool.server.main import main
from browser_tool.server.tool_runner import (
    INTERNAL_ERROR,
    SCRUB_FAILED,
    SCRUB_FAILED_AFTER_ACTION,
    ToolRunner,
)
from browser_tool.server.wiring import BACKEND_DOCKER, BACKEND_LOCAL, build_context

__all__ = [
    "BACKEND_DOCKER",
    "BACKEND_LOCAL",
    "DOCKER_INSTRUCTIONS",
    "DOCKER_SERVER_NAME",
    "INSTRUCTIONS",
    "INTERNAL_ERROR",
    "SCRUB_FAILED",
    "SCRUB_FAILED_AFTER_ACTION",
    "SERVER_NAME",
    "ToolRunner",
    "build_context",
    "build_server",
    "main",
]
