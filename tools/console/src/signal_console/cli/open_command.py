"""`console open`: make sure the server runs, then open the page in an Edge app window.

It talks as it goes: a page that isn't built stops it at once with the one
command to run (setup is the one builder; open never builds), the server start
says what happens (cli/server_start.py), and before the window opens it prints
every health row that isn't ok.

The page URL carries a one-time login key in its fragment (/#k=<key>), which
the server issues to local callers holding .state/local-key. `--view setup` (with
`--tool <id>`) adds `&v=setup&t=<id>`, so `setup` and `/setup` open straight on the wizard.
"""

import os
import re
import webbrowser
from urllib.parse import urlencode

from signal_console.cli.doctor_command import doctor_line
from signal_console.cli.server_start import OpenError, login_key, start_server
from signal_console.health import OK, SETUP_COMMAND, HealthPaths, health_rows
from signal_console.launch import clean_env, spawn_detached
from signal_console.local_api import server_port
from signal_console.paths import LOOPBACK_HOST, TOOL_ROOT

# Views the page can open on (web/src/state/reducer.ts View), and the tool id shape.
OPEN_VIEWS = ("scope", "chat", "voice", "boards", "tasks", "system", "setup")
_TOOL_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


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


def open_console(paths: HealthPaths, view: str | None = None, tool: str | None = None) -> str:
    """Start the server if needed and open the console page.

    Args:
        paths: This checkout's files (HealthPaths()); `default_port` is the port for a
            server this starts (a running one keeps its own).
        view: The view to open on (OPEN_VIEWS), or None for the scope.
        tool: With view "setup", the tool whose steps the wizard opens at.

    Returns:
        The page address (without the login key).

    Raises:
        OpenError: The page isn't built, the server didn't start (with why), or no
            browser could be opened.
        ValueError: A bad view or tool id.
    """
    page_fragment("check", view, tool)  # validate before starting anything
    if not (paths.web_dist_dir / "index.html").is_file():
        raise OpenError(
            "the console's page isn't built yet. Build it from the repo root with "
            f"{SETUP_COMMAND}, then run console open again"
        )
    key = login_key(paths.state_dir) or start_server(paths)
    for row in health_rows(paths):
        if row.level != OK:
            print(doctor_line(row))
    page = f"http://{LOOPBACK_HOST}:{server_port(paths.state_dir)}/"
    _open_window(paths, f"{page}#{page_fragment(key, view, tool)}")
    return page


def _open_window(paths: HealthPaths, url: str) -> None:
    if not paths.edge_path.is_file():
        # No Edge: the default browser still gets a normal window.
        if not webbrowser.open(url):
            raise OpenError(f"Edge isn't at {paths.edge_path}; open {url} within a minute")
        return
    with open(os.devnull, "wb") as no_output:
        # Detached, so a first Edge window survives the shell that ran `console open`.
        spawn_detached(
            [str(paths.edge_path), f"--app={url}"], TOOL_ROOT, no_output, clean_env(os.environ)
        )
