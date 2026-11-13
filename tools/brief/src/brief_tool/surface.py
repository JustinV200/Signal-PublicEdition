"""Which surface this process serves, from SIGNAL_BRIEF_SURFACE.

The sessions daemon sets it to "managed" for the headless sessions it runs, so
their brief tools and prompt hook never ack anything: the owner isn't watching them.
Unset (a normal Claude Code session) is "session". .mcp.json never sets it.
"""

from collections.abc import Mapping

SURFACE_ENV = "SIGNAL_BRIEF_SURFACE"
MANAGED = "managed"
SESSION = "session"


def brief_surface(environ: Mapping[str, str]) -> str:
    """The surface: MANAGED when the sessions daemon started this session, else SESSION."""
    return MANAGED if environ.get(SURFACE_ENV, "").strip() == MANAGED else SESSION
