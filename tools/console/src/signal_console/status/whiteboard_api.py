"""Where the whiteboard daemon listens and how to ask it for JSON (read-only, token in a header).

The daemon (tools/whiteboard) records its port in .state/daemon.json and its
API token in .state/token, which it wants as X-Signal-Token. The token only
ever goes in that header to the daemon's loopback port; it never reaches the
console's page. Shared by the boards reader, the devices page and the camera
stream proxy. The console never starts the daemon.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp

from signal_console.paths import LOOPBACK_HOST, WHITEBOARD_STATE_DIR
from signal_console.state_files import read_json, read_secret

TOKEN_HEADER = "X-Signal-Token"
# The daemon's files in its state folder.
WHITEBOARD_DAEMON_FILE = "daemon.json"
WHITEBOARD_TOKEN_FILE = "token"
REQUEST_TIMEOUT_S = 1.5


@dataclass(frozen=True)
class WhiteboardTarget:
    """A daemon's address and token. repr leaves the token out, so a log line can't leak it."""

    base_url: str
    token: str

    def __repr__(self) -> str:
        return f"WhiteboardTarget({self.base_url!r})"

    @property
    def headers(self) -> dict[str, str]:
        """The auth header the daemon wants."""
        return {TOKEN_HEADER: self.token}


def find_whiteboard(state_dir: Path = WHITEBOARD_STATE_DIR) -> WhiteboardTarget | None:
    """The daemon's address and token from its files, or None if either is missing."""
    daemon = read_json(state_dir / WHITEBOARD_DAEMON_FILE)
    token = read_secret(state_dir / WHITEBOARD_TOKEN_FILE)
    port = daemon.get("port") if daemon else None
    if not isinstance(port, int) or isinstance(port, bool) or token is None:
        return None
    return WhiteboardTarget(f"http://{LOOPBACK_HOST}:{port}", token)


async def get_whiteboard_json(
    session: aiohttp.ClientSession, target: WhiteboardTarget, path: str
) -> dict[str, Any]:
    """GET one /api path from the daemon and return its JSON object.

    Raises:
        aiohttp.ClientError: It refused, errored or isn't there.
        TimeoutError: No answer within REQUEST_TIMEOUT_S.
        ValueError: The answer isn't a JSON object.
    """
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_S)
    url = f"{target.base_url}{path}"
    async with session.get(url, headers=target.headers, timeout=timeout) as response:
        response.raise_for_status()
        payload = await response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"{path} didn't return a JSON object")
    return payload
