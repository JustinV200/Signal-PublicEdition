"""The server rows: is this checkout's console server running, and is its port free for it?

Both are local reads. The server counts as running only while the process
daemon.json records (pid and start time) still runs (local_api.server_port).
The port row looks up who listens on the port without connecting to it, so
no key or token can reach a listener that isn't this checkout's own server.
"""

from signal_console.health.inputs import HealthPaths
from signal_console.health.port_holder import PortHolder, find_port_holder
from signal_console.health.row import ATTENTION, OK, HealthRow
from signal_console.local_api import server_port
from signal_console.open_hint import open_command
from signal_console.paths import DAEMON_FILE
from signal_console.state_files import read_json


def server_rows(paths: HealthPaths) -> list[HealthRow]:
    """The server row, then the port row ("another checkout's console holds the port")."""
    port = server_port(paths.state_dir)
    if port is None:
        server = HealthRow(
            "server",
            "Console server",
            ATTENTION,
            "not running",
            "The console server isn't running.",
            "Start it and open the console window with this command (it runs from any folder).",
            open_command(paths.tool_root),
        )
    else:
        words = f"The console server is running on port {port}."
        server = HealthRow("server", "Console server", OK, "running", words)
    return [server, port_row(paths)]


def port_row(paths: HealthPaths) -> HealthRow:
    """The port row: ok when the port is free or this checkout's running server holds it.

    `console open` asks this before it starts a server, so a port another checkout's
    console holds is reported at once instead of after a failed start.
    """
    own_port = server_port(paths.state_dir)
    # Our own server's port while it runs, else the one `console open` would use.
    port = own_port or paths.default_port
    holder = find_port_holder(port)
    own_pid = (read_json(paths.state_dir / DAEMON_FILE) or {}).get("pid") if own_port else None
    if holder is None or holder.pid == own_pid:
        if holder is None:
            return HealthRow("port", "Console port", OK, "free", f"Port {port} is free.")
        return HealthRow("port", "Console port", OK, "ours", f"Port {port} is this console's.")
    return HealthRow(
        "port",
        "Console port",
        ATTENTION,
        "taken",
        _holder_words(holder, port, paths),
        # No command: "<a free port>" isn't runnable, so it stays in the fix's words.
        "Stop that program, or run `console open --port <a free port>`.",
    )


def _holder_words(holder: PortHolder, port: int, paths: HealthPaths) -> str:
    project = holder.project
    if project is not None and project.resolve() == paths.tool_root.resolve():
        # This checkout's own server, but daemon.json is gone or names another process.
        return (
            f"Port {port} is held by a console server from this checkout (pid {holder.pid}) "
            "that daemon.json doesn't name."
        )
    # A checkout's console runs from <checkout>/tools/console/.venv.
    if project is not None and [p.casefold() for p in project.parts[-2:]] == ["tools", "console"]:
        checkout = project.parent.parent
        return f"Port {port} is held by the console of another checkout, {checkout}."
    if project is not None:
        return f"Port {port} is held by a program running from {project}."
    # Without a readable path, the program's name (or nothing) is all there is to go on.
    named = f" ({holder.program})" if holder.program else ""
    return f"Another program{named} holds port {port}."
