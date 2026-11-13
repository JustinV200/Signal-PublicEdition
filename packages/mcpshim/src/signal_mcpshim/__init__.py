"""Public API of signal_mcpshim: a stdio proxy that respawns a dead MCP server.

The `mcpshim` command (cli.main) is what .mcp.json runs; Shim and ShimTimings are the
relay itself, for tests or embedding.
"""

from signal_mcpshim.cli import main
from signal_mcpshim.shim import Shim
from signal_mcpshim.timings import ShimTimings

__all__ = ["Shim", "ShimTimings", "main"]
