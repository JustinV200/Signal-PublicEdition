"""OpenRGB.exe's command line, run through a console-less cmd.exe: start the server, save a profile.

OpenRGB.exe attaches to its parent's console, so started straight from sleepmode it
would write into a terminal and be ended when that terminal closes. A cmd.exe started
with DETACHED_PROCESS has no console to offer, so OpenRGB runs on its own.

Saving goes through the CLI because OpenRGB 1.0's server only lets its own "local
client" (SDK protocol 6) save profiles, and openrgb-python speaks protocol 4 at most.
The CLI connects to the running server as that local client (its default
autoconnect, with no --client: that adds a second connection, and every device is
then saved twice).
"""

import logging
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from openrgb import OpenRGBClient

from sleepmode.config import OPENRGB_CLI_TIMEOUT_S
from sleepmode.shared import popen_detached

log = logging.getLogger(__name__)

SERVER_ARGS = ("--server", "--startminimized")
_DETACHED = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

# Opens a fresh SDK client, or answers None if the server isn't up.
Connect = Callable[[], OpenRGBClient | None]


def start_server(exe_path: Path) -> None:
    """Start OpenRGB's SDK server, detached, in the tray. It's left running for good.

    Raises:
        OSError: cmd.exe couldn't be started, or exe_path has a % (see _command_line).
    """
    # `start`: cmd hands OpenRGB off and exits, instead of waiting on it all day.
    command = _command_line(exe_path, SERVER_ARGS, prefix='start "" ')
    popen_detached(command, _DETACHED, exe_path.parent)
    log.info("lighting: starting %s %s", exe_path, " ".join(SERVER_ARGS))


def save_profile(
    exe_path: Path | None, client: OpenRGBClient, name: str, *, connect: Connect
) -> OpenRGBClient:
    """Save the running server's look as a profile, and check that the server lists it.

    The client is closed first: once a profile is saved, OpenRGB 1.0 sends its SDK
    clients a notice openrgb-python can't parse, and that connection's next request
    then stalls 10 s and fails.

    Args:
        exe_path: OpenRGB.exe.
        client: The SDK client in use; it's disconnected.
        name: The profile name.
        connect: Opens a fresh SDK client, or answers None if the server is gone.

    Returns:
        A fresh client, connected after the save (the caller disconnects it).

    Raises:
        OSError: OpenRGB.exe isn't there or its path has a %, the CLI failed or timed
            out, the server went away, or it doesn't list the profile afterwards.
    """
    if exe_path is None or not exe_path.is_file():
        raise FileNotFoundError(f"can't save the {name} profile: {exe_path} isn't there")
    client.disconnect()
    _run_cli(exe_path, ("-sp", name))
    fresh = connect()
    if fresh is None:
        raise ConnectionError(f"OpenRGB's server went away while saving the {name} profile")
    if not any(profile.name.lower() == name.lower() for profile in fresh.profiles):
        fresh.disconnect()
        raise OSError(f"OpenRGB didn't save the {name} profile")
    log.info("lighting: saved the OpenRGB look as %s", name)
    return fresh


def _run_cli(exe_path: Path, args: tuple[str, ...]) -> None:
    """Run OpenRGB.exe's CLI to the end (it connects to the running server by itself).

    Raises:
        OSError: It failed or timed out.
    """
    try:
        # shortcut: a timeout ends cmd.exe but not a hung OpenRGB.exe under it; put both
        # in a job object if that's ever seen.
        subprocess.run(
            _command_line(exe_path, args),
            cwd=exe_path.parent,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_DETACHED,
            timeout=OPENRGB_CLI_TIMEOUT_S,
            check=True,
        )
    except subprocess.SubprocessError as error:
        raise OSError(f"OpenRGB.exe {' '.join(args)} failed: {error}") from error


def _command_line(exe_path: Path, args: tuple[str, ...], prefix: str = "") -> str:
    """`cmd.exe /d /s /c "<prefix>"OpenRGB.exe" args"`; /s makes cmd strip only the outer quotes.

    The exe path is always quoted: list2cmdline quotes only on spaces, and cmd.exe
    would split an unquoted path at a `&` or `|` in a folder name.

    Raises:
        OSError: exe_path has a %. cmd.exe expands %NAME% even inside quotes, and has
            no escape for it there; it ends up as a note asking to move OpenRGB.
    """
    if "%" in str(exe_path):
        raise OSError(
            f"cmd.exe can't run {exe_path} safely, since it would expand the % in it; "
            "move OpenRGB to a folder without a % and set [lighting] openrgb_path"
        )
    cmd_exe = Path(os.environ.get("SYSTEMROOT", r"C:\Windows"), "System32", "cmd.exe")
    line = f'"{exe_path}" {subprocess.list2cmdline(args)}'
    return f'"{cmd_exe}" /d /s /c "{prefix}{line}"'
