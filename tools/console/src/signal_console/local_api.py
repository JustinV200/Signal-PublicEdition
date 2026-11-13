"""POST to the running console server as a local process (the turn hook, `console open`).

Local routes skip the page's session token and take the key in
.state/local-key instead, sent as X-Console-Key. Stdlib plus psutil (about 20 ms
to import, for server_port's liveness check), so the hook still starts fast.
"""

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from signal_console.paths import DAEMON_FILE, LOCAL_KEY_FILE, LOCAL_KEY_HEADER, LOOPBACK_HOST
from signal_console.process_record import find_recorded_process
from signal_console.state_files import read_json, read_secret

HOOK_TURN_PATH = "/api/hook/turn"
LOGIN_KEY_PATH = "/api/local/login-key"
# The server refuses a request body larger than this (413); senders keep under it.
MAX_BODY_BYTES = 64 * 1024

# Never route loopback calls through a system proxy.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class ConsoleNotRunningError(RuntimeError):
    """No console server answers: no live daemon.json or no key, or nothing listening."""


def server_port(state_dir: Path) -> int | None:
    """The port in daemon.json, or None unless the server that wrote it is still running.

    A server that crashed leaves daemon.json behind, and by then any program may
    hold its port. Checking that the recorded process (pid and start time) still
    runs means the local key and the hook's replies never go to whatever answers
    there instead: while that server runs, the port is its own.
    """
    daemon = read_json(state_dir / DAEMON_FILE) or {}
    port, pid, create_time = daemon.get("port"), daemon.get("pid"), daemon.get("createTime")
    if not isinstance(port, int) or not isinstance(pid, int):
        return None
    if not isinstance(create_time, int | float) or find_recorded_process(pid, create_time) is None:
        return None
    return port


def post_local(
    state_dir: Path, path: str, body: dict[str, Any], timeout_s: float
) -> dict[str, Any]:
    """POST a JSON body to a local route of the running server.

    Args:
        state_dir: The console's .state folder (daemon.json and local-key).
        path: The route, e.g. "/api/hook/turn".
        body: The JSON body.
        timeout_s: Connect and read timeout.

    Returns:
        The JSON reply.

    Raises:
        ConsoleNotRunningError: No running server is recorded, or none is listening.
        urllib.error.HTTPError: The server refused the request.
        OSError, ValueError: The request failed midway or the reply wasn't JSON.
    """
    port = server_port(state_dir)
    key = read_secret(state_dir / LOCAL_KEY_FILE)
    if port is None or key is None:
        raise ConsoleNotRunningError("no console server has started")
    request = urllib.request.Request(
        f"http://{LOOPBACK_HOST}:{port}{path}",
        # Raw UTF-8 rather than \u escapes, so a body's size is what its text costs.
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", LOCAL_KEY_HEADER: key},
        method="POST",
    )
    try:
        with _OPENER.open(request, timeout=timeout_s) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError:
        # HTTPError is a URLError, but a refusal (401, 403, 413) means the server is up:
        # pass it on rather than report the console as not running.
        raise
    except urllib.error.URLError as error:
        raise ConsoleNotRunningError(
            f"the console server isn't answering ({error.reason})"
        ) from error
