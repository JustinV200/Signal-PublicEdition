"""open_openrgb: connect to OpenRGB's SDK server (127.0.0.1:6742), starting it if it isn't running.

A server sleepmode starts is left running for good: it holds the lighting state, so
it knows the colours it set (it can't read some devices' colours
back), and a later snapshot is right. It runs as `OpenRGB.exe --server
--startminimized` (openrgb_cli.start_server), so it sits in the tray, and its window
is where the `day` profile is changed and saved.
"""

import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from openrgb import OpenRGBClient

from sleepmode.config import (
    OPENRGB_DEFAULT_PARTS,
    OPENRGB_HOST,
    OPENRGB_PORT,
    OPENRGB_SETTLE_S,
    OPENRGB_START_TIMEOUT_S,
)
from sleepmode.lighting.openrgb_cli import save_profile, start_server

log = logging.getLogger(__name__)

# The name the server lists for this client.
CLIENT_NAME = "sleepmode"
# Protocol 3 has profile list and load. 4 adds a plugin-list request that OpenRGB 1.0's
# server can leave unanswered, which would cost a 10 s socket timeout on every connect.
PROTOCOL_VERSION = 3
POLL_S = 0.25


@dataclass
class OpenRgbSession:
    """A connected SDK client.

    Attributes:
        client: The openrgb-python client in use; close() disconnects it.
        started_server: True if sleepmode just started the server (it stays running).
        save_with_cli: (client, name) saves the server's look as a profile and returns
            a fresh client (openrgb_cli.save_profile); raises OSError.
    """

    client: OpenRGBClient
    started_server: bool
    save_with_cli: Callable[[OpenRGBClient, str], OpenRGBClient]

    def save_profile(self, name: str) -> None:
        """Save the server's current look as `name`; `client` is a new connection after.

        Raises:
            OSError: It wasn't saved (see openrgb_cli.save_profile).
        """
        self.client = self.save_with_cli(self.client, name)

    def close(self) -> None:
        """Disconnect the client in use (safe to repeat)."""
        self.client.disconnect()


def resolve_openrgb_path(configured: str) -> Path | None:
    """OpenRGB.exe: the configured path, else the portable install under %LOCALAPPDATA%.

    Returns None when neither is set (no LOCALAPPDATA).
    """
    if configured:
        return Path(configured)
    local_app_data = os.environ.get("LOCALAPPDATA")
    return Path(local_app_data, *OPENRGB_DEFAULT_PARTS) if local_app_data else None


def open_openrgb(exe_path: Path | None) -> OpenRgbSession | None:
    """Connect to the SDK server, starting OpenRGB first if nothing is listening.

    Args:
        exe_path: OpenRGB.exe, to start the server and to save profiles.

    Returns:
        The session, or None when no server is running and OpenRGB.exe isn't there
        (logged at INFO: nothing to do).

    Raises:
        OSError: OpenRGB couldn't be started, or its server didn't come up in time
            (TimeoutError).
    """
    client = _try_connect()
    started_server = client is None
    if client is None:
        if exe_path is None or not exe_path.is_file():
            log.info("lighting: OpenRGB's server isn't running and %s isn't there; skip", exe_path)
            return None
        start_server(exe_path)
        client = _wait_until_ready(time.monotonic() + OPENRGB_START_TIMEOUT_S)
        log.info("lighting: sleepmode started OpenRGB's server; it stays running")
    save_with_cli = partial(save_profile, exe_path, connect=_try_connect)
    return OpenRgbSession(client, started_server, save_with_cli)


def _try_connect() -> OpenRGBClient | None:
    """A client with the device and profile lists loaded, or None if the server isn't up.

    openrgb-python times its connect out after 1 s and each reply after 10 s.
    """
    # TODO: a read that spins inside OpenRGBClient() (the server closed mid-reply) has no
    # session yet, so an abandoned step's StepGuard can't close its socket, and it runs
    # until the process ends. Fix: subclass NetworkClient to register its socket first.
    try:
        return OpenRGBClient(OPENRGB_HOST, OPENRGB_PORT, CLIENT_NAME, PROTOCOL_VERSION)
    except OSError:  # refused, timed out, or dropped mid-handshake (OpenRGBDisconnected)
        return None


def _wait_until_ready(deadline: float) -> OpenRGBClient:
    """Connect once the server listens, then wait for its device list to settle.

    Raises:
        TimeoutError: The server didn't listen before the deadline.
    """
    while (client := _try_connect()) is None:
        if time.monotonic() >= deadline:
            raise TimeoutError(f"OpenRGB's server isn't up after {OPENRGB_START_TIMEOUT_S:g} s")
        time.sleep(POLL_S)
    _wait_for_devices(client, deadline)
    return client


def _wait_for_devices(client: OpenRGBClient, deadline: float) -> None:
    """Poll the device count until it holds for OPENRGB_SETTLE_S (or the deadline passes).

    The server listens before detection ends (2 of 4 devices at first on this PC).
    """
    count, since = len(client.devices), time.monotonic()
    while time.monotonic() < deadline:
        time.sleep(POLL_S)
        client.update()
        if len(client.devices) != count:
            count, since = len(client.devices), time.monotonic()
        elif time.monotonic() - since >= OPENRGB_SETTLE_S:
            return
    log.warning("lighting: OpenRGB was still finding devices at the deadline; using %d", count)
