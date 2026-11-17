"""daemon.json: where the running daemon listens and its token, readable by its owner only.

The icacls lock-down is copied from tools/sessions (tokens/token_file.py);
tools never import each other. The file is created and locked down before the
token goes in, and rewritten in place (not replaced), so the secret is never
readable under the folder's inherited permissions.
"""

import getpass
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_FILE_NAME = "daemon.json"
# The only address the daemon binds and its clients dial.
LOOPBACK_HOST = "127.0.0.1"
OWNER_ONLY_MODE = 0o600


@dataclass(frozen=True)
class DaemonState:
    """What a client needs to reach the daemon.

    Attributes:
        port: The loopback port.
        token: The bearer token.
        pid: The daemon's process id.
    """

    port: int
    token: str
    pid: int


def write_state(state_dir: Path, state: DaemonState) -> Path:
    """Write daemon.json, owner-only.

    Raises:
        OSError: The file couldn't be written.
    """
    path = state_dir / STATE_FILE_NAME
    state_dir.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    _restrict_to_owner(path)
    body = {"port": state.port, "token": state.token, "pid": state.pid}
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def read_state(state_dir: Path) -> DaemonState | None:
    """The running daemon's state, or None if daemon.json is missing or malformed."""
    path = state_dir / STATE_FILE_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = DaemonState(int(data["port"]), str(data["token"]), int(data["pid"]))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError) as error:
        logger.warning("can't read %s: %s", path, error)
        return None
    return state


def remove_state(state_dir: Path, token: str) -> None:
    """Delete daemon.json unless a newer daemon has since replaced it."""
    current = read_state(state_dir)
    if current is not None and current.token == token:
        (state_dir / STATE_FILE_NAME).unlink(missing_ok=True)


def _restrict_to_owner(path: Path) -> None:
    """Limit the file to the current user; log (don't fail) if that isn't possible."""
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
            "couldn't restrict %s to %s (icacls: %s); other local users may read the token",
            path,
            account,
            (completed.stdout + completed.stderr).strip(),
        )
