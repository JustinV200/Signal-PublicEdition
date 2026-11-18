"""Which process listens on a port, and which project folder it runs from. Read-only.

The doctor asks this when the port this checkout's console uses is held by a
process daemon.json doesn't name: usually another checkout's console (two
checkouts both default to 8790). It reads the OS's listening-socket table and
the process's own paths. Nothing connects to the port, so no key or token is
ever sent to whatever holds it.

Checked on Windows without elevation: every listener's pid and exe can be read;
a system or elevated process's command line can't (AccessDenied), and then only
the pid and program name are known.
"""

import contextlib
import logging
from dataclasses import dataclass
from pathlib import Path

import psutil

# A listener on these addresses blocks a 127.0.0.1 bind; one on another interface doesn't.
BLOCKING_ADDRESSES = frozenset({"127.0.0.1", "0.0.0.0", "::"})
VENV_FOLDER = ".venv"
# uv's venv python.exe starts the base interpreter as a child, so the venv path is
# on the listener's parent: look this many parents up.
PARENTS_TO_READ = 2

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PortHolder:
    """A process listening on the port.

    Attributes:
        pid: Its pid.
        program: Its exe's file name, or "" when even that can't be read.
        project: The folder holding the .venv it runs from (e.g. a checkout's
            tools/console), or None when no readable path names one.
    """

    pid: int
    program: str
    project: Path | None


def find_port_holder(port: int) -> PortHolder | None:
    """The process listening on `port` on loopback (or all addresses), if any.

    Returns:
        The holder, or None when nothing listens there or the socket table
        can't be read (logged as a warning).
    """
    try:
        connections = psutil.net_connections(kind="tcp")
    except psutil.Error as error:
        log.warning("can't read the listening sockets (%s); the port check is skipped", error)
        return None
    for connection in connections:
        address = connection.laddr
        is_listening = connection.status == psutil.CONN_LISTEN and connection.pid
        blocks_bind = address and address.port == port and address.ip in BLOCKING_ADDRESSES
        if is_listening and blocks_bind:
            return _describe(connection.pid)
    return None


def project_from_paths(paths: list[str]) -> Path | None:
    """The folder that holds the first .venv named in `paths` (exe or command-line parts)."""
    for text in paths:
        parts = Path(text).parts
        lowered = [part.casefold() for part in parts]
        if VENV_FOLDER in lowered:
            return Path(*parts[: lowered.index(VENV_FOLDER)])
    return None


def _describe(pid: int) -> PortHolder:
    try:
        process = psutil.Process(pid)
        program = Path(process.exe()).name
    except psutil.Error:
        # Gone, or not readable without elevation: only the pid is known.
        return PortHolder(pid, "", None)
    return PortHolder(pid, program, project_from_paths(_readable_paths(process)))


def _readable_paths(process: psutil.Process) -> list[str]:
    # The exe and command line of the process and its parents, skipping what can't be read.
    paths: list[str] = []
    try:
        chain = [process, *process.parents()[:PARENTS_TO_READ]]
    except psutil.Error:
        chain = [process]
    # AccessDenied (a system or elevated process) just means less to go on: use the rest.
    for member in chain:
        with contextlib.suppress(psutil.Error):
            paths.append(member.exe())
        with contextlib.suppress(psutil.Error):
            paths += member.cmdline()
    return paths
