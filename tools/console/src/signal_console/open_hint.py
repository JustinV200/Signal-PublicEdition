"""The `console open` command line the page shows when it is signed out or the server is down.

The server fills in its own absolute project path, so the line runs from any
folder and opens this checkout's console (two checkouts on one PC each name
their own). The path is in double quotes because it can contain spaces. It
names a folder, never a key or token, so it is safe in an unauthenticated 401.
Stdlib only.
"""

from pathlib import Path

from signal_console.paths import TOOL_ROOT


def open_command(tool_root: Path = TOOL_ROOT) -> str:
    """The full command that starts the server if needed and opens a signed-in window.

    Args:
        tool_root: The console's project folder (tools/console); tests pass a fake one.

    Returns:
        `uv run --project "<tool_root>" --frozen --no-sync console open`.
    """
    return f'uv run --project "{tool_root}" --frozen --no-sync console open'
