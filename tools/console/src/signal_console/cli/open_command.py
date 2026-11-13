"""`console open`: make sure the server runs, then open the page in an Edge app window.

The page URL carries a one-time login key in its fragment (/#k=<key>), which
the server issues to local callers holding .state/local-key. `--view setup` (with
`--tool <id>`) adds `&v=setup&t=<id>`, so `setup` and `/setup` open straight on the wizard.
"""

import os
import re
import sys
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

from signal_console.launch import clean_env, spawn_detached
from signal_console.local_api import (
    LOGIN_KEY_PATH,
    ConsoleNotRunningError,
    post_local,
    server_port,
)
from signal_console.paths import LOOPBACK_HOST, SERVER_LOG_FILE, TOOL_ROOT
from signal_console.state_files import ensure_state_dir

EDGE_PATH = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
REQUEST_TIMEOUT_S = 2.0
STARTUP_TIMEOUT_S = 15.0
POLL_INTERVAL_S = 0.25
# Views the page can open on (web/src/state/reducer.ts View), and the tool id shape.
OPEN_VIEWS = ("scope", "chat", "voice", "boards", "tasks", "devices", "models", "setup", "tools")
_TOOL_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


class OpenError(RuntimeError):
    """The server didn't come up, or Edge couldn't be started."""


def page_fragment(key: str, view: str | None = None, tool: str | None = None) -> str:
    """The URL fragment: the login key, then the view and tool to open on, if any.

    Raises:
        ValueError: An unknown view or a malformed tool id.
    """
    if view is not None and view not in OPEN_VIEWS:
        raise ValueError(f"unknown view {view!r}; choose from {', '.join(OPEN_VIEWS)}")
    if tool is not None and not _TOOL_ID.match(tool):
        raise ValueError(f"bad tool id {tool!r}")
    extra = {"v": view, "t": tool}
    return urlencode({"k": key, **{k: v for k, v in extra.items() if v}})


def open_console(
    state_dir: Path, port: int, view: str | None = None, tool: str | None = None
) -> str:
    """Start the server if needed and open the console page.

    Args:
        state_dir: The console's .state folder.
        port: The port for a server this starts (a running one keeps its own).
        view: The view to open on (OPEN_VIEWS), or None for the scope.
        tool: With view "setup", the tool whose steps the wizard opens at.

    Returns:
        The page address (without the login key).

    Raises:
        OpenError: The server didn't answer in time, or no browser could be opened.
        ValueError: A bad view or tool id.
    """
    page_fragment("check", view, tool)  # validate before starting anything
    key = _login_key(state_dir)
    if key is None:
        _start_server(state_dir, port)
        key = _wait_for_login_key(state_dir)
    page = f"http://{LOOPBACK_HOST}:{server_port(state_dir)}/"
    url = f"{page}#{page_fragment(key, view, tool)}"
    if not EDGE_PATH.is_file():
        # No Edge: the default browser still gets a normal window.
        if not webbrowser.open(url):
            raise OpenError(f"Edge isn't at {EDGE_PATH}; open {url} within a minute")
        return page
    with open(os.devnull, "wb") as no_output:
        # Detached, so a first Edge window survives the shell that ran `console open`.
        spawn_detached(
            [str(EDGE_PATH), f"--app={url}"], TOOL_ROOT, no_output, clean_env(os.environ)
        )
    return page


def _login_key(state_dir: Path) -> str | None:
    try:
        reply = post_local(state_dir, LOGIN_KEY_PATH, {}, REQUEST_TIMEOUT_S)
    except ConsoleNotRunningError:
        return None
    key = reply.get("key")
    if not isinstance(key, str):
        raise OpenError("the console server gave no login key")
    return key


def _start_server(state_dir: Path, port: int) -> None:
    ensure_state_dir(state_dir)
    command = [sys.executable, "-m", "signal_console", "serve", "--port", str(port)]
    with (state_dir / SERVER_LOG_FILE).open("ab") as log_file:
        spawn_detached(command, TOOL_ROOT, log_file, clean_env(os.environ))


def _wait_for_login_key(state_dir: Path) -> str:
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_S)
        key = _login_key(state_dir)
        if key is not None:
            return key
    raise OpenError(
        f"the console server didn't start within {STARTUP_TIMEOUT_S:.0f} s; "
        f"see {state_dir / SERVER_LOG_FILE}"
    )
