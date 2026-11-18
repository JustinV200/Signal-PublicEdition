"""The files and folders the health checks read: the real ones by default, temp ones in tests."""

from dataclasses import dataclass, field
from pathlib import Path

from signal_console.paths import (
    DEFAULT_PORT,
    EDGE_PATH,
    LOCAL_SETTINGS_PATH,
    PROJECT_SETTINGS_PATH,
    STATE_DIR,
    TOOL_ROOT,
    WEB_DIST_DIR,
    WHITEBOARD_STATE_DIR,
)


@dataclass(frozen=True)
class HealthPaths:
    """Where each check looks. Every check only reads these; none is ever written.

    Attributes:
        state_dir: The console's .state folder (daemon.json, the claim, the logs).
        web_dist_dir: The built page (web/dist).
        settings_files: Claude Code's project settings, then the local settings (hooks).
        edge_path: msedge.exe, which `console open` starts.
        whiteboard_dir: The whiteboard daemon's .state folder.
        tool_root: This checkout's tools/console, named in the fix commands.
        default_port: The port `console open` uses when no server of ours runs.
    """

    state_dir: Path = STATE_DIR
    web_dist_dir: Path = WEB_DIST_DIR
    settings_files: tuple[Path, ...] = field(default=(PROJECT_SETTINGS_PATH, LOCAL_SETTINGS_PATH))
    edge_path: Path = EDGE_PATH
    whiteboard_dir: Path = WHITEBOARD_STATE_DIR
    tool_root: Path = TOOL_ROOT
    default_port: int = DEFAULT_PORT
