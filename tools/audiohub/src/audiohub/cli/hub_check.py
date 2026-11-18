"""`audiohub check`: the setup window's health check. Read-only, fast, never starts the hub.

Installed is proven by this command running. Whether the voice hub daemon is up is read
from its own signs: the IPC token file it writes while it runs, plus a bare connect (no
data sent) to its loopback port. A hub that crashed leaves the token but nothing listens,
so both must hold. A different program on the port without the token reads as not running.
It can't tell a healthy hub from a stuck one that still accepts connections.
"""

import argparse
import json
import socket
from pathlib import Path

from audiohub.cli.command import Command
from audiohub.config import Settings
from audiohub.kernel.ipc.auth_token import DEFAULT_TOKEN_PATH

EXIT_OK = 0
CONNECT_TIMEOUT_S = 1.0
RUN_HUB = "uv run --env-file .env --project tools/audiohub --frozen --no-sync audiohub run"


def is_hub_running(host: str, port: int, token_path: Path = DEFAULT_TOKEN_PATH) -> bool:
    """True when the hub's token file exists and its IPC port accepts a connection.

    Args:
        host: The hub's IPC host (settings.ipc.host).
        port: The hub's IPC port.
        token_path: The file the running hub writes its token to.
    """
    if not token_path.is_file():
        return False
    try:
        # Connect and close with no bytes sent: the server treats that as an empty line.
        with socket.create_connection((host, port), timeout=CONNECT_TIMEOUT_S):
            return True
    except OSError:
        return False


def run(args: argparse.Namespace, settings: Settings) -> int:
    """Print the summary JSON line. Exit 0 either way: a stopped hub is a state, not a break."""
    if is_hub_running(settings.ipc.host, settings.ipc.port):
        summary = {"words": "Voice hub is running"}
    else:
        summary = {
            "words": "Installed, but the voice hub isn't running",
            "fix": "Start it with Start voice in the console.",
            "command": RUN_HUB,
        }
    print(json.dumps(summary))
    return EXIT_OK


COMMAND = Command(
    name="check",
    help="health check: installed, and whether the voice hub is running (starts nothing)",
    add_arguments=lambda parser: None,
    run=run,
)
