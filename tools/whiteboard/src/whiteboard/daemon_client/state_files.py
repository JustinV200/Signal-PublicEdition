"""The daemon's discovery files in .state/: daemon.json (pid + port) and token (API secret).

The daemon writes both on start and removes daemon.json on a clean exit; the
MCP server and CLI read them to find the daemon and authenticate. The token
stops other local web pages from driving the API (CSRF): a page can POST to
127.0.0.1 but can't read this file.
"""

import getpass
import json
import logging
import os
import secrets
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from signal_jsonstate import read_bytes_retrying, write_json_atomic

DAEMON_INFO_FILE = "daemon.json"
TOKEN_FILE = "token"
LOG_FILE = "daemon.log"
# 32 random bytes, URL-safe base64: plenty against guessing over loopback.
TOKEN_BYTES = 32
OWNER_ONLY_MODE = 0o600

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DaemonInfo:
    """What a running daemon says about itself.

    Attributes:
        pid: The daemon's process id.
        port: The loopback port its HTTP server listens on.
        started_at: Unix time it started.
    """

    pid: int
    port: int
    started_at: float


def write_daemon_info(state_dir: Path, port: int) -> DaemonInfo:
    """Record this process as the running daemon.

    Args:
        state_dir: The .state/ folder.
        port: The port the server is listening on.

    Returns:
        The info written.
    """
    info = DaemonInfo(pid=os.getpid(), port=port, started_at=time.time())
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {"pid": info.pid, "port": info.port, "started_at": info.started_at}
    # Atomic, so the CLI, MCP server, console and sleepmode never read it half-written.
    write_json_atomic(state_dir / DAEMON_INFO_FILE, payload)
    return info


def read_daemon_info(state_dir: Path) -> DaemonInfo | None:
    """Read daemon.json, or None if it's missing or unreadable (no daemon recorded)."""
    try:
        payload = json.loads(read_bytes_retrying(state_dir / DAEMON_INFO_FILE))
        return DaemonInfo(int(payload["pid"]), int(payload["port"]), float(payload["started_at"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def remove_daemon_info(state_dir: Path) -> None:
    """Delete daemon.json if it still names this process (a newer daemon may have replaced it)."""
    info = read_daemon_info(state_dir)
    if info is not None and info.pid == os.getpid():
        (state_dir / DAEMON_INFO_FILE).unlink(missing_ok=True)


def create_token(state_dir: Path) -> str:
    """Generate a fresh API token and write it to .state/token.

    Args:
        state_dir: The .state/ folder.

    Returns:
        The token the daemon must require.
    """
    path = state_dir / TOKEN_FILE
    state_dir.mkdir(parents=True, exist_ok=True)
    # Lock the file down before the secret goes in, so it's never readable under
    # the folder's inherited permissions (Users / Authenticated Users on Windows).
    path.touch(exist_ok=True)
    _restrict_to_owner(path)
    token = secrets.token_urlsafe(TOKEN_BYTES)
    path.write_text(token, encoding="utf-8")
    return token


def read_token(state_dir: Path) -> str | None:
    """Read the API token, or None if no daemon has written one."""
    try:
        token = (state_dir / TOKEN_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return token or None


def _restrict_to_owner(path: Path) -> None:
    """Limit a file to the current user; log (don't fail) if that isn't possible.

    Same sequence as tools/sessions' token_file.py (separate projects share no code).
    """
    if os.name != "nt":
        path.chmod(OWNER_ONLY_MODE)
        return
    user = getpass.getuser()
    domain = os.environ.get("USERDOMAIN")
    account = f"{domain}\\{user}" if domain else user
    # Drop inherited entries and grant full control to this user alone.
    command = ["icacls", str(path), "/inheritance:r", "/grant:r", f"{account}:F"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        logger.warning(
            "Couldn't restrict %s to %s (icacls: %s); other local users may read the token",
            path,
            account,
            (completed.stdout + completed.stderr).strip(),
        )
