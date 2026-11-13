"""Fixed filesystem locations for the sessions tool: its root, its state folder and the files in it.

The state folder (`tools/sessions/.state/`, gitignored) holds the daemon's
persisted session metadata, its IPC token and the background daemon's log.
Settings may point it elsewhere (tests do), so everything else takes the
folder as a parameter. The voice hub's token is written by tools/audiohub.
"""

from pathlib import Path

# src/claude_sessions/config/paths.py -> parents: config, claude_sessions, src, tools/sessions.
TOOL_ROOT = Path(__file__).resolve().parents[3]
# tools/sessions -> tools -> the Signal repo root.
REPO_ROOT = TOOL_ROOT.parents[1]

DEFAULT_STATE_DIR = TOOL_ROOT / ".state"
# audiohub writes its kernel's IPC token here each time the hub starts.
DEFAULT_HUB_TOKEN_FILE = REPO_ROOT / "tools" / "audiohub" / ".cache" / "ipc-token"

SESSIONS_FILE_NAME = "sessions.json"
DAEMON_LOG_FILE_NAME = "daemon.log"
DAEMON_TOKEN_FILE_NAME = "token"
# Lives here, not in settings.py, because the token file name depends on it.
DEFAULT_DAEMON_PORT = 8766


def sessions_file(state_dir: Path) -> Path:
    """Where the daemon persists managed-session metadata.

    Args:
        state_dir: The tool's state folder.

    Returns:
        The path of `sessions.json` inside it.
    """
    return state_dir / SESSIONS_FILE_NAME


def daemon_log_file(state_dir: Path) -> Path:
    """Where a daemon started in the background writes its stdout and stderr.

    Args:
        state_dir: The tool's state folder.

    Returns:
        The path of `daemon.log` inside it.
    """
    return state_dir / DAEMON_LOG_FILE_NAME


def daemon_token_file(state_dir: Path, port: int) -> Path:
    """Where the daemon on this port writes the secret token every IPC request must carry.

    Named per port, so a daemon on another port never replaces the default
    daemon's token. The default port keeps the plain name the running daemon uses.

    Args:
        state_dir: The tool's state folder.
        port: The daemon's TCP port.

    Returns:
        The path of `token` (default port) or `token-<port>` inside it.
    """
    if port == DEFAULT_DAEMON_PORT:
        return state_dir / DAEMON_TOKEN_FILE_NAME
    return state_dir / f"{DAEMON_TOKEN_FILE_NAME}-{port}"
